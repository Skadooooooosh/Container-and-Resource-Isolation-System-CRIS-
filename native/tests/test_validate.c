#include <assert.h>
#include <stdio.h>
#include "cris_validate.h"
int main(void) {
    assert(cris_valid_hostname("demo-1"));
    assert(!cris_valid_hostname("")); assert(!cris_valid_hostname("-x")); assert(!cris_valid_hostname("a b"));
    assert(!cris_valid_hostname("x;rm"));
    assert(cris_valid_cgroup_path("/sys/fs/cgroup/user.slice/cris-abc"));
    assert(!cris_valid_cgroup_path("/etc/passwd"));
    assert(!cris_valid_cgroup_path("/sys/fs/cgroup/../../etc"));
    assert(!cris_valid_cgroup_path("/sys/fs/cgroup/a/.."));
    int f;
    assert(cris_parse_ns("pid,mnt,uts", &f) == 0 && (f & CLONE_NEWPID) && (f & CLONE_NEWNS) && (f & CLONE_NEWUTS));
    assert(cris_parse_ns("", &f) == 0 && f == 0);
    assert(cris_parse_ns("pid,bogus", &f) == -1);
    puts("native validation tests: OK");
    return 0;
}
