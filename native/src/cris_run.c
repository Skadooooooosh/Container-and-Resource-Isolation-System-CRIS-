/*
 * cris_run - CRIS native container launcher.
 *
 * Creates the requested Linux namespaces with clone(2), attaches the child to a
 * pre-configured cgroup v2 directory BEFORE it executes the workload, acts as
 * PID 1 (reaper) when a PID namespace is requested, enforces a wall-clock
 * timeout, and emits machine-readable JSON events on --event-fd.
 *
 * Usage: cris_run [--ns pid,mnt,uts,ipc,net,user] [--cgroup DIR] [--hostname H]
 *                 [--timeout SEC] [--event-fd N] -- CMD [ARGS...]
 *        cris_run --probe        (report which namespaces can be created)
 * Exit: workload code | 128+sig | 124 timeout | 2 usage | 3 cgroup | 4 clone
 */
#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif
#include <errno.h>
#include <fcntl.h>
#include <sched.h>
#include <signal.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mount.h>
#include <sys/prctl.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>
#include "cris_validate.h"

#define STACK_SIZE (1024 * 1024)

struct opts {
    int flags;
    const char *cgroup, *hostname;
    int timeout, event_fd;
    char **cmd;
    int sync_fd[2];
};

static volatile sig_atomic_t g_timeout = 0, g_term = 0;
static pid_t g_child = -1;

static void emit(int fd, const char *fmt, ...) {
    if (fd < 0) return;
    va_list ap; va_start(ap, fmt); vdprintf(fd, fmt, ap); va_end(ap);
}
static void on_term(int s) { (void)s; g_term = 1; if (g_child > 0) kill(g_child, SIGKILL); }
static void on_alarm(int s) { (void)s; g_timeout = 1; if (g_child > 0) kill(g_child, SIGKILL); }

static int write_file(const char *path, const char *data) {
    int fd = open(path, O_WRONLY | O_CLOEXEC);
    if (fd < 0) return -1;
    ssize_t n = write(fd, data, strlen(data));
    int saved = errno; close(fd); errno = saved;
    return n < 0 ? -1 : 0;
}

static int child_fn(void *arg) {
    struct opts *o = arg;
    prctl(PR_SET_PDEATHSIG, SIGKILL);          /* launcher death => ns init dies => whole ns torn down */
    close(o->sync_fd[1]);
    char c;
    if (read(o->sync_fd[0], &c, 1) != 1) _exit(120);   /* parent aborted before cgroup/uid setup */
    close(o->sync_fd[0]);

    if (o->flags & CLONE_NEWNS)
        if (mount(NULL, "/", NULL, MS_REC | MS_PRIVATE, NULL) != 0)
            emit(o->event_fd, "{\"event\":\"warning\",\"what\":\"make-rprivate\",\"errno\":%d}\n", errno);
    if ((o->flags & CLONE_NEWNS) && (o->flags & CLONE_NEWPID))
        if (mount("proc", "/proc", "proc", MS_NOSUID | MS_NODEV | MS_NOEXEC, NULL) != 0)
            emit(o->event_fd, "{\"event\":\"warning\",\"what\":\"mount-proc\",\"errno\":%d}\n", errno);
    if ((o->flags & CLONE_NEWUTS) && o->hostname)
        if (sethostname(o->hostname, strlen(o->hostname)) != 0)
            emit(o->event_fd, "{\"event\":\"warning\",\"what\":\"sethostname\",\"errno\":%d}\n", errno);

    if (!(o->flags & CLONE_NEWPID)) { execvp(o->cmd[0], o->cmd); _exit(127); }

    /* PID 1 of a new PID namespace: run the workload as a child and reap every
     * orphan re-parented to us until the main workload exits. */
    pid_t w = fork();
    if (w < 0) _exit(126);
    if (w == 0) { execvp(o->cmd[0], o->cmd); _exit(127); }
    int st = 0;
    for (;;) {
        int ws; pid_t r = wait(&ws);
        if (r == w) { st = ws; break; }
        if (r < 0 && errno == EINTR) continue;
        if (r < 0) break;
    }
    _exit(WIFEXITED(st) ? WEXITSTATUS(st) : 128 + WTERMSIG(st));
}

static int probe_child(void *arg) {
    (void)arg;
    return 0;
}

static int probe_flags(int flags) {
    char *stk = malloc(STACK_SIZE);
    if (!stk) return ENOMEM;
    int f = flags | SIGCHLD;
    if (!(flags & CLONE_NEWUSER) && geteuid() != 0) f |= CLONE_NEWUSER;
    pid_t p = clone(probe_child, stk + STACK_SIZE, f, NULL);
    int e = 0;
    if (p < 0) e = errno; else waitpid(p, NULL, 0);
    free(stk);
    return e;
}

static int probe_one(int flag) {
    return probe_flags(flag);
}

static int do_probe(void) {
    int comb_def = probe_flags(CLONE_NEWPID | CLONE_NEWNS | CLONE_NEWUTS | CLONE_NEWIPC);
    int comb_all = probe_flags(CLONE_NEWPID | CLONE_NEWNS | CLONE_NEWUTS | CLONE_NEWIPC | CLONE_NEWNET);
    printf("{\"euid\":%d,\"user\":%d,\"pid\":%d,\"mnt\":%d,\"uts\":%d,\"ipc\":%d,\"net\":%d,\"combined_default\":%d,\"combined_all\":%d}\n",
           (int)geteuid(), probe_one(CLONE_NEWUSER), probe_one(CLONE_NEWPID), probe_one(CLONE_NEWNS),
           probe_one(CLONE_NEWUTS), probe_one(CLONE_NEWIPC), probe_one(CLONE_NEWNET),
           comb_def, comb_all);
    return 0;
}

static int usage(void) {
    fprintf(stderr, "usage: cris_run [--ns LIST] [--cgroup DIR] [--hostname H] [--timeout S] [--event-fd N] -- CMD...\n"
                    "       cris_run --probe\n");
    return 2;
}

int main(int argc, char **argv) {
    struct opts o = { .event_fd = -1 };
    const char *nslist = "";
    int i = 1;
    if (argc == 2 && !strcmp(argv[1], "--probe")) return do_probe();
    for (; i < argc; i++) {
        if (!strcmp(argv[i], "--")) { i++; break; }
        if (i + 1 >= argc) return usage();
        if (!strcmp(argv[i], "--ns")) nslist = argv[++i];
        else if (!strcmp(argv[i], "--cgroup")) o.cgroup = argv[++i];
        else if (!strcmp(argv[i], "--hostname")) o.hostname = argv[++i];
        else if (!strcmp(argv[i], "--timeout")) o.timeout = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--event-fd")) o.event_fd = atoi(argv[++i]);
        else return usage();
    }
    if (i >= argc) return usage();
    o.cmd = &argv[i];
    if (cris_parse_ns(nslist, &o.flags) != 0) { fprintf(stderr, "bad --ns\n"); return 2; }
    if (o.hostname && !cris_valid_hostname(o.hostname)) { fprintf(stderr, "bad hostname\n"); return 2; }
    if (o.cgroup && !cris_valid_cgroup_path(o.cgroup)) { fprintf(stderr, "bad cgroup path\n"); return 2; }
    if (o.timeout < 0 || o.timeout > 3600) { fprintf(stderr, "bad timeout\n"); return 2; }

    if (pipe2(o.sync_fd, O_CLOEXEC) != 0) { perror("pipe"); return 4; }
    char *stk = malloc(STACK_SIZE);
    if (!stk) return 4;

    struct sigaction sa;                    /* no SA_RESTART: waitpid must see EINTR */
    memset(&sa, 0, sizeof sa);
    sa.sa_handler = on_term; sigaction(SIGTERM, &sa, NULL); sigaction(SIGINT, &sa, NULL);
    sa.sa_handler = on_alarm; sigaction(SIGALRM, &sa, NULL);

    pid_t child = clone(child_fn, stk + STACK_SIZE, o.flags | SIGCHLD, &o);
    if (child < 0) {
        emit(o.event_fd, "{\"event\":\"error\",\"stage\":\"clone\",\"errno\":%d,\"msg\":\"%s\"}\n", errno, strerror(errno));
        return 4;
    }
    g_child = child;
    char path[128], buf[64];

    if (o.flags & CLONE_NEWUSER) {          /* map our uid/gid to root inside the user namespace */
        snprintf(path, sizeof path, "/proc/%d/setgroups", child); write_file(path, "deny");
        snprintf(path, sizeof path, "/proc/%d/gid_map", child);
        snprintf(buf, sizeof buf, "0 %d 1", (int)getegid());
        int r1 = write_file(path, buf);
        snprintf(path, sizeof path, "/proc/%d/uid_map", child);
        snprintf(buf, sizeof buf, "0 %d 1", (int)geteuid());
        int r2 = write_file(path, buf);
        if (r1 || r2) {
            emit(o.event_fd, "{\"event\":\"error\",\"stage\":\"uidmap\",\"errno\":%d,\"msg\":\"%s\"}\n", errno, strerror(errno));
            kill(child, SIGKILL); waitpid(child, NULL, 0); return 4;
        }
    }
    int attached = 0;
    if (o.cgroup) {                         /* attach BEFORE the workload runs; failure is fatal, never silent */
        snprintf(path, sizeof path, "%s/cgroup.procs", o.cgroup);
        snprintf(buf, sizeof buf, "%d", (int)child);
        if (write_file(path, buf) != 0) {
            emit(o.event_fd, "{\"event\":\"error\",\"stage\":\"cgroup\",\"errno\":%d,\"msg\":\"%s\"}\n", errno, strerror(errno));
            kill(child, SIGKILL); waitpid(child, NULL, 0); return 3;
        }
        attached = 1;
    }
    emit(o.event_fd, "{\"event\":\"started\",\"host_pid\":%d,\"launcher_pid\":%d,\"cgroup_attached\":%s,\"ns_flags\":%d}\n",
         (int)child, (int)getpid(), attached ? "true" : "false", o.flags);
    if (o.timeout > 0) alarm((unsigned)o.timeout);
    if (write(o.sync_fd[1], "g", 1) != 1) kill(child, SIGKILL);
    close(o.sync_fd[1]);

    int st = 0;
    for (;;) {
        pid_t r = waitpid(child, &st, 0);
        if (r < 0 && errno == EINTR) continue;
        break;
    }
    int code = WIFEXITED(st) ? WEXITSTATUS(st) : 128 + WTERMSIG(st);
    int sig = WIFSIGNALED(st) ? WTERMSIG(st) : 0;
    emit(o.event_fd, "{\"event\":\"exit\",\"code\":%d,\"signal\":%d,\"timeout\":%s,\"terminated\":%s}\n",
         code, sig, g_timeout ? "true" : "false", g_term ? "true" : "false");
    return g_timeout ? 124 : code;
}
