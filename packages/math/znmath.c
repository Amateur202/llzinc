#define M_PI 3.14159265358979323846
#define M_PI_2 1.57079632679489661923

double _zn_sqrt(double x) {
    if (x <= 0) return 0;
    double guess = x / 2;
    for (int i = 0; i < 50; i++)
        guess = (guess + x / guess) / 2;
    return guess;
}

double _zn_sin(double x) {
    double term = x, sum = x;
    for (int i = 1; i < 12; i++) {
        term *= -x * x / ((2*i) * (2*i+1));
        sum += term;
    }
    return sum;
}

double _zn_cos(double x) {
    double term = 1, sum = 1;
    for (int i = 1; i < 12; i++) {
        term *= -x * x / ((2*i-1) * (2*i));
        sum += term;
    }
    return sum;
}

double _zn_log(double x) {
    if (x <= 0) return -1e308;
    double y = (x - 1) / (x + 1), y2 = y * y;
    double sum = y, term = y;
    for (int i = 1; i < 50; i++) {
        term *= y2;
        sum += term / (2 * i + 1);
    }
    return 2 * sum;
}

double _zn_exp(double x) {
    double sum = 1, term = 1;
    for (int i = 1; i < 30; i++) {
        term *= x / i;
        sum += term;
    }
    return sum;
}

double _zn_atan(double x) {
    if (x > 1) return M_PI_2 - _zn_atan(1.0 / x);
    if (x < -1) return -M_PI_2 - _zn_atan(1.0 / x);
    double term = x, sum = x, x2 = x * x;
    for (int i = 1; i < 50; i++) {
        term *= -x2;
        sum += term / (2 * i + 1);
    }
    return sum;
}

double _zn_atan2(double y, double x) {
    if (x > 0) return _zn_atan(y / x);
    if (x < 0) return y >= 0 ? _zn_atan(y / x) + M_PI : _zn_atan(y / x) - M_PI;
    if (y > 0) return M_PI_2;
    if (y < 0) return -M_PI_2;
    return 0;
}

double _zn_asin(double x) {
    if (x > 1 || x < -1) return 0;
    return _zn_atan(x / _zn_sqrt(1 - x * x));
}

double _zn_acos(double x) {
    return M_PI_2 - _zn_asin(x);
}

double _zn_tan(double x) {
    return _zn_sin(x) / _zn_cos(x);
}

double _zn_sinh(double x) {
    double e = _zn_exp(x);
    return (e - 1.0 / e) / 2;
}

double _zn_cosh(double x) {
    double e = _zn_exp(x);
    return (e + 1.0 / e) / 2;
}

double _zn_tanh(double x) {
    double e = _zn_exp(x);
    double inv_e = 1.0 / e;
    return (e - inv_e) / (e + inv_e);
}

double _zn_asinh(double x) {
    return _zn_log(x + _zn_sqrt(x * x + 1));
}

double _zn_acosh(double x) {
    if (x < 1) return 0;
    return _zn_log(x + _zn_sqrt(x * x - 1));
}

double _zn_atanh(double x) {
    if (x <= -1 || x >= 1) return 0;
    return 0.5 * _zn_log((1 + x) / (1 - x));
}

double _zn_pow(double x, double y) {
    if (y == 0) return 1;
    if (x == 0) return 0;
    long n = (long)y;
    if (y == (double)n) {
        double result = 1;
        long abs_n = n < 0 ? -n : n;
        for (long i = 0; i < abs_n; i++)
            result *= x;
        return n < 0 ? 1.0 / result : result;
    }
    if (x < 0) return 0;
    return _zn_exp(y * _zn_log(x));
}

double _zn_exp2(double x) {
    return _zn_pow(2.0, x);
}

double _zn_exp10(double x) {
    return _zn_pow(10.0, x);
}

double _zn_log2(double x) {
    return _zn_log(x) / 0.6931471805599453;
}

double _zn_log10(double x) {
    return _zn_log(x) / 2.3025850929940459;
}

double _zn_log1p(double x) {
    return _zn_log(1 + x);
}

double _zn_cbrt(double x) {
    if (x < 0) return -_zn_pow(-x, 1.0 / 3.0);
    return _zn_pow(x, 1.0 / 3.0);
}

double _zn_hypot(double x, double y) {
    return _zn_sqrt(x * x + y * y);
}

double _zn_floor(double x) {
    long n = (long)x;
    return (double)(x >= 0 ? n : (x == n ? n : n - 1));
}

double _zn_ceil(double x) {
    long n = (long)x;
    return (double)(x >= 0 ? (x == n ? n : n + 1) : n);
}

double _zn_round(double x) {
    if (x >= 0) return (double)(long)(x + 0.5);
    return (double)(long)(x - 0.5);
}

double _zn_trunc(double x) {
    return (double)(long)x;
}

double _zn_rint(double x) {
    return _zn_round(x);
}

double _zn_nearbyint(double x) {
    return _zn_round(x);
}

double _zn_fabs(double x) {
    return x < 0 ? -x : x;
}

double _zn_fmod(double x, double y) {
    if (y == 0) return 0;
    return x - y * (long)(x / y);
}

double _zn_remainder(double x, double y) {
    if (y == 0) return 0;
    double n = _zn_round(x / y);
    return x - n * y;
}

double _zn_fdim(double x, double y) {
    return x > y ? x - y : 0;
}

double _zn_fmax(double x, double y) {
    return x > y ? x : y;
}

double _zn_fmin(double x, double y) {
    return x < y ? x : y;
}

double _zn_fma(double x, double y, double z) {
    return x * y + z;
}

double _zn_copysign(double x, double y) {
    if (y >= 0) return _zn_fabs(x);
    return -_zn_fabs(x);
}
