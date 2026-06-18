#include <stdint.h>
#include <time.h>
#include <errno.h>

double _zn_time_now() {
    struct timespec ts;
    clock_gettime(CLOCK_REALTIME, &ts);
    return (double)ts.tv_sec + (double)ts.tv_nsec / 1e9;
}

double _zn_time_ms() {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec * 1000.0 + (double)ts.tv_nsec / 1e6;
}

void _zn_time_sleep(double secs) {
    struct timespec ts;
    ts.tv_sec = (time_t)secs;
    ts.tv_nsec = (long)((secs - (double)ts.tv_sec) * 1e9);
    while (nanosleep(&ts, &ts) == -1 && errno == EINTR);
}

int64_t _zn_time_year(int64_t t) {
    time_t tt = (time_t)t;
    struct tm result;
    localtime_r(&tt, &result);
    return result.tm_year + 1900;
}

int64_t _zn_time_month(int64_t t) {
    time_t tt = (time_t)t;
    struct tm result;
    localtime_r(&tt, &result);
    return result.tm_mon + 1;
}

int64_t _zn_time_day(int64_t t) {
    time_t tt = (time_t)t;
    struct tm result;
    localtime_r(&tt, &result);
    return result.tm_mday;
}

int64_t _zn_time_hour(int64_t t) {
    time_t tt = (time_t)t;
    struct tm result;
    localtime_r(&tt, &result);
    return result.tm_hour;
}

int64_t _zn_time_min(int64_t t) {
    time_t tt = (time_t)t;
    struct tm result;
    localtime_r(&tt, &result);
    return result.tm_min;
}

int64_t _zn_time_sec(int64_t t) {
    time_t tt = (time_t)t;
    struct tm result;
    localtime_r(&tt, &result);
    return result.tm_sec;
}
