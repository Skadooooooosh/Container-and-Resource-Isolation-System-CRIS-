/* Pure, side-effect-free validation helpers (unit-tested in tests/test_validate.c). */
#ifndef CRIS_VALIDATE_H
#define CRIS_VALIDATE_H
#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif
#include <ctype.h>
#include <sched.h>
#include <stdlib.h>
#include <string.h>

/* 1..63 chars of [A-Za-z0-9-], not starting/ending with '-'. */
static inline int cris_valid_hostname(const char *h) {
    size_t n = h ? strlen(h) : 0;
    if (n == 0 || n > 63 || h[0] == '-' || h[n - 1] == '-') return 0;
    for (size_t i = 0; i < n; i++)
        if (!isalnum((unsigned char)h[i]) && h[i] != '-') return 0;
    return 1;
}

/* cgroup path must live under /sys/fs/cgroup and contain no ".." component. */
static inline int cris_valid_cgroup_path(const char *p) {
    static const char pre[] = "/sys/fs/cgroup/";
    if (!p || strncmp(p, pre, sizeof(pre) - 1) != 0) return 0;
    if (strstr(p, "/../")) return 0;
    size_t n = strlen(p);
    if (n >= 3 && strcmp(p + n - 3, "/..") == 0) return 0;
    return n < 4096;
}

/* Parse "pid,mnt,uts,ipc,net,user" into clone() flags. Returns -1 on unknown token. */
static inline int cris_parse_ns(const char *list, int *flags) {
    char buf[128];
    if (!list || strlen(list) >= sizeof(buf)) return -1;
    strcpy(buf, list);
    *flags = 0;
    if (buf[0] == '\0') return 0;
    for (char *tok = strtok(buf, ","); tok; tok = strtok(NULL, ",")) {
        if (!strcmp(tok, "pid")) *flags |= CLONE_NEWPID;
        else if (!strcmp(tok, "mnt")) *flags |= CLONE_NEWNS;
        else if (!strcmp(tok, "uts")) *flags |= CLONE_NEWUTS;
        else if (!strcmp(tok, "ipc")) *flags |= CLONE_NEWIPC;
        else if (!strcmp(tok, "net")) *flags |= CLONE_NEWNET;
        else if (!strcmp(tok, "user")) *flags |= CLONE_NEWUSER;
        else return -1;
    }
    return 0;
}
#endif
