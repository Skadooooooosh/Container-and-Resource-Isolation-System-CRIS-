/*
 * cris_workload - bounded, predefined workloads. Hard caps everywhere; prints
 * exactly one JSON result line on completion ("progress ..." lines are interim).
 *   cpu     --iterations N --seconds S      fixed work, wall-clock capped
 *   memory  --mb N --seconds S              allocate+touch N MiB (cap 512)
 *   process --procs N --seconds S           fork up to N (cap 64) sleeping children
 *   mixed   --mb N --iterations N --seconds S
 *   idle    --seconds S
 *   nsinfo                                  report pid/hostname/ns inodes/visible pids
 */
#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif
#include <ctype.h>
#include <dirent.h>
#include <errno.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

#define MAX_MB 512
#define MAX_PROCS 64
#define MAX_SECONDS 3600

static double now(clockid_t c) { struct timespec t; clock_gettime(c, &t); return (double)t.tv_sec + (double)t.tv_nsec / 1e9; }
static long argl(int argc, char **argv, const char *k, long def, long lo, long hi) {
    for (int i = 2; i + 1 < argc; i++)
        if (!strcmp(argv[i], k)) {
            char *e; long v = strtol(argv[i + 1], &e, 10);
            if (*e || v < lo || v > hi) { fprintf(stderr, "invalid %s (allowed %ld..%ld)\n", k, lo, hi); exit(2); }
            return v;
        }
    return def;
}

static int run_cpu(long iters, long max_s, uint64_t *sum, double *wall) {
    double t0 = now(CLOCK_MONOTONIC);
    uint64_t x = 88172645463325252ULL, acc = 0; int trunc = 0;
    for (long i = 0; i < iters; i++) {
        x ^= x << 13; x ^= x >> 7; x ^= x << 17; acc += x;
        if ((i & 0xFFFFF) == 0 && now(CLOCK_MONOTONIC) - t0 > (double)max_s) { trunc = 1; break; }
    }
    *sum = acc; *wall = now(CLOCK_MONOTONIC) - t0;
    return trunc;
}

static long alloc_touch(long mb) {
    long n = 0;
    for (; n < mb; n++) {
        char *p = malloc(1 << 20);
        if (!p) break;
        memset(p, 0xA5, 1 << 20);                 /* touch => resident => charged to the cgroup */
        if ((n + 1) % 8 == 0) { printf("progress allocated_mb=%ld\n", n + 1); fflush(stdout); }
    }
    return n;                                      /* blocks intentionally kept until exit */
}

static void nsinfo(void) {
    const char *names[] = { "pid", "mnt", "uts", "ipc", "net", "user" };
    char host[256] = "", path[64], val[128];
    gethostname(host, sizeof host);
    printf("{\"workload\":\"nsinfo\",\"pid\":%d,\"ppid\":%d,\"uid\":%d,\"hostname\":\"%s\",\"ns\":{",
           (int)getpid(), (int)getppid(), (int)getuid(), host);
    for (int i = 0; i < 6; i++) {
        snprintf(path, sizeof path, "/proc/self/ns/%s", names[i]);
        ssize_t n = readlink(path, val, sizeof val - 1);
        if (n < 0) n = 0;
        val[n] = 0;
        printf("%s\"%s\":\"%s\"", i ? "," : "", names[i], val);
    }
    int visible = 0; DIR *d = opendir("/proc");
    if (d) { struct dirent *e; while ((e = readdir(d))) if (isdigit((unsigned char)e->d_name[0])) visible++; closedir(d); }
    printf("},\"visible_pids\":%d}\n", visible);
}

int main(int argc, char **argv) {
    if (argc < 2) { fprintf(stderr, "usage: cris_workload TYPE [opts]\n"); return 2; }
    const char *t = argv[1];
    long secs = argl(argc, argv, "--seconds", 5, 1, MAX_SECONDS);
    if (!strcmp(t, "nsinfo")) { nsinfo(); return 0; }
    if (!strcmp(t, "idle")) {
        sleep((unsigned)secs);
        printf("{\"workload\":\"idle\",\"seconds\":%ld}\n", secs); return 0;
    }
    if (!strcmp(t, "cpu")) {
        long it = argl(argc, argv, "--iterations", 300000000L, 1000, 4000000000L);
        uint64_t s; double w, c0 = now(CLOCK_PROCESS_CPUTIME_ID);
        int tr = run_cpu(it, secs, &s, &w);
        printf("{\"workload\":\"cpu\",\"iterations\":%ld,\"wall_sec\":%.4f,\"cpu_sec\":%.4f,\"truncated\":%s,\"checksum\":%llu}\n",
               it, w, now(CLOCK_PROCESS_CPUTIME_ID) - c0, tr ? "true" : "false", (unsigned long long)s);
        return 0;
    }
    if (!strcmp(t, "memory") || !strcmp(t, "mixed")) {
        long mb = argl(argc, argv, "--mb", 64, 1, MAX_MB);
        double t0 = now(CLOCK_MONOTONIC);
        long got = alloc_touch(mb);
        double cpu_w = 0; uint64_t s = 0; int tr = 0;
        if (!strcmp(t, "mixed")) tr = run_cpu(argl(argc, argv, "--iterations", 100000000L, 1000, 4000000000L), secs, &s, &cpu_w);
        else sleep((unsigned)(secs > 3 ? 3 : secs));
        printf("{\"workload\":\"%s\",\"requested_mb\":%ld,\"allocated_mb\":%ld,\"wall_sec\":%.4f,\"cpu_wall_sec\":%.4f,\"truncated\":%s}\n",
               t, mb, got, now(CLOCK_MONOTONIC) - t0, cpu_w, tr ? "true" : "false");
        return got == mb ? 0 : 1;
    }
    if (!strcmp(t, "process")) {
        long n = argl(argc, argv, "--procs", 8, 1, MAX_PROCS), ok = 0; int err = 0;
        pid_t kids[MAX_PROCS];
        for (long i = 0; i < n; i++) {
            pid_t p = fork();
            if (p < 0) { err = errno; break; }
            if (p == 0) { sleep((unsigned)secs); _exit(0); }
            kids[ok++] = p;
        }
        printf("{\"workload\":\"process\",\"requested\":%ld,\"forked\":%ld,\"fork_errno\":%d,\"fork_error\":\"%s\",\"self_pid\":%d}\n",
               n, ok, err, err ? strerror(err) : "", (int)getpid());
        fflush(stdout);
        for (long i = 0; i < ok; i++) kill(kids[i], SIGTERM);     /* bounded: always clean up own children */
        for (long i = 0; i < ok; i++) waitpid(kids[i], NULL, 0);
        return 0;
    }
    fprintf(stderr, "unknown workload '%s'\n", t);
    return 2;
}
