#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <unistd.h>
#include <sys/stat.h>
#include <dirent.h>
#include <errno.h>

typedef struct { char *data; int64_t len; } zn_string;

int64_t _zn_os_cmd(zn_string cmd) {
    char *buf = strndup(cmd.data, cmd.len);
    if (!buf) return -1;
    int rc = system(buf);
    free(buf);
    return rc;
}

zn_string _zn_os_cmd_output(zn_string cmd) {
    char *buf = strndup(cmd.data, cmd.len);
    if (!buf) return (zn_string){0, 0};
    FILE *fp = popen(buf, "r");
    free(buf);
    if (!fp) return (zn_string){0, 0};
    size_t cap = 4096, len = 0;
    char *out = malloc(cap);
    if (!out) { pclose(fp); return (zn_string){0, 0}; }
    size_t n;
    while ((n = fread(out + len, 1, cap - len, fp)) > 0) {
        len += n;
        if (cap - len < 256) {
            cap *= 2;
            char *tmp = realloc(out, cap);
            if (!tmp) { free(out); pclose(fp); return (zn_string){0, 0}; }
            out = tmp;
        }
    }
    pclose(fp);
    out[len] = 0;
    return (zn_string){out, len};
}

zn_string _zn_os_list(zn_string path) {
    char *buf = strndup(path.data, path.len);
    if (!buf) return (zn_string){0, 0};
    DIR *d = opendir(buf);
    free(buf);
    if (!d) return (zn_string){0, 0};
    size_t cap = 4096, len = 0;
    char *out = malloc(cap);
    if (!out) { closedir(d); return (zn_string){0, 0}; }
    struct dirent *e;
    while ((e = readdir(d))) {
        if (!strcmp(e->d_name, ".") || !strcmp(e->d_name, "..")) continue;
        size_t slen = strlen(e->d_name);
        if (len + slen + 1 > cap) {
            cap = (len + slen + 1) * 2;
            char *tmp = realloc(out, cap);
            if (!tmp) { free(out); closedir(d); return (zn_string){0, 0}; }
            out = tmp;
        }
        if (len > 0) out[len++] = '\n';
        memcpy(out + len, e->d_name, slen);
        len += slen;
    }
    closedir(d);
    out[len] = 0;
    return (zn_string){out, len};
}

int64_t _zn_os_mkdir(zn_string path) {
    char *buf = strndup(path.data, path.len);
    if (!buf) return -1;
    int rc = mkdir(buf, 0755);
    free(buf);
    return rc;
}

int64_t _zn_os_rmdir(zn_string path) {
    char *buf = strndup(path.data, path.len);
    if (!buf) return -1;
    int rc = rmdir(buf);
    free(buf);
    return rc;
}

int64_t _zn_os_remove(zn_string path) {
    char *buf = strndup(path.data, path.len);
    if (!buf) return -1;
    int rc = unlink(buf);
    free(buf);
    return rc;
}

int64_t _zn_os_rename(zn_string from, zn_string to) {
    char *fbuf = strndup(from.data, from.len);
    char *tbuf = strndup(to.data, to.len);
    if (!fbuf || !tbuf) { free(fbuf); free(tbuf); return -1; }
    int rc = rename(fbuf, tbuf);
    free(fbuf); free(tbuf);
    return rc;
}

int8_t _zn_os_exists(zn_string path) {
    char *buf = strndup(path.data, path.len);
    if (!buf) return 0;
    struct stat st;
    int rc = stat(buf, &st);
    free(buf);
    return rc == 0 ? 1 : 0;
}

int8_t _zn_os_is_dir(zn_string path) {
    char *buf = strndup(path.data, path.len);
    if (!buf) return 0;
    struct stat st;
    int rc = stat(buf, &st);
    free(buf);
    return rc == 0 && S_ISDIR(st.st_mode) ? 1 : 0;
}

int8_t _zn_os_is_file(zn_string path) {
    char *buf = strndup(path.data, path.len);
    if (!buf) return 0;
    struct stat st;
    int rc = stat(buf, &st);
    free(buf);
    return rc == 0 && S_ISREG(st.st_mode) ? 1 : 0;
}

zn_string _zn_os_cwd() {
    long size = pathconf(".", _PC_PATH_MAX);
    if (size < 0) size = 4096;
    char *buf = malloc(size);
    if (!buf) return (zn_string){0, 0};
    if (!getcwd(buf, size)) { free(buf); return (zn_string){0, 0}; }
    int64_t len = strlen(buf);
    return (zn_string){buf, len};
}

int64_t _zn_os_chdir(zn_string path) {
    char *buf = strndup(path.data, path.len);
    if (!buf) return -1;
    int rc = chdir(buf);
    free(buf);
    return rc;
}

zn_string _zn_os_getenv(zn_string name) {
    char *buf = strndup(name.data, name.len);
    if (!buf) return (zn_string){0, 0};
    char *val = getenv(buf);
    free(buf);
    if (!val) return (zn_string){0, 0};
    int64_t len = strlen(val);
    char *cpy = malloc(len);
    if (!cpy) return (zn_string){0, 0};
    memcpy(cpy, val, len);
    return (zn_string){cpy, len};
}

int64_t _zn_os_setenv(zn_string name, zn_string val) {
    char *nbuf = strndup(name.data, name.len);
    char *vbuf = strndup(val.data, val.len);
    if (!nbuf || !vbuf) { free(nbuf); free(vbuf); return -1; }
    int rc = setenv(nbuf, vbuf, 1);
    free(nbuf); free(vbuf);
    return rc;
}

int64_t _zn_os_pid() {
    return (int64_t)getpid();
}

zn_string _zn_os_hostname() {
    long size = sysconf(_SC_HOST_NAME_MAX);
    if (size < 0) size = 256;
    char *buf = malloc(size + 1);
    if (!buf) return (zn_string){0, 0};
    if (gethostname(buf, size + 1)) { free(buf); return (zn_string){0, 0}; }
    int64_t len = strlen(buf);
    return (zn_string){buf, len};
}

void _zn_os_exit(int64_t code) {
    exit((int)code);
}
