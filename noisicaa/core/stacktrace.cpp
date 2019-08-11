/*
 * @custom_license
 *
 * Based on libsegfault, with some local modifications (Linux compatibility, formatting, remove
 * unused code).
 *
 * Original license:
 *
 * Copyright (C) 2015 Stanislav Sedov <stas@FreeBSD.org>
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions
 * are met:
 * 1. Redistributions of source code must retain the above copyright
 *    notice, this list of conditions and the following disclaimer.
 * 2. Redistributions in binary form must reproduce the above copyright
 *    notice, this list of conditions and the following disclaimer in the
 *    documentation and/or other materials provided with the distribution.
 *
 * THIS SOFTWARE IS PROVIDED BY THE AUTHOR AND CONTRIBUTORS ``AS IS'' AND
 * ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
 * ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR OR CONTRIBUTORS BE LIABLE
 * FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
 * DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
 * OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
 * HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
 * LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
 * OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
 * SUCH DAMAGE.
 *
 */

#include <sys/types.h>

#include <err.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ucontext.h>
#include <unistd.h>
#include <pthread.h>

#include <unwind.h>
#include <libunwind.h>

#define	BACKTRACE_DEPTH	256
#define	NULLSTR	"(null)"

namespace noisicaa {

static inline void print_str(int fd, const char *str) {
  if (str == NULL) {
    write(fd, NULLSTR, strlen(NULLSTR));
  } else {
    write(fd, str, strlen(str));
  }
}

static void print_unw_error(const char *fun, int error) {
  print_str(STDERR_FILENO, fun);
  print_str(STDERR_FILENO, ": ");
  print_str(STDERR_FILENO, unw_strerror(error));
  print_str(STDERR_FILENO, "\n");
}

static int print_stack_trace(ucontext_t *context) {
  unw_cursor_t cursor;
  unw_word_t backtrace[BACKTRACE_DEPTH];
  unw_word_t ip, off;
  char buf[1024];
  unsigned int level;
  int ret;

  if ((ret = unw_init_local(&cursor, context)) != 0) {
    print_unw_error("unw_init_local", ret);
    return (1);
  }

  print_str(STDERR_FILENO, "frame IP                 function\n");
  level = 0;
  ret = 0;
  for (;;) {
    char name[128];

    if (level >= BACKTRACE_DEPTH)
      break;
    unw_get_reg(&cursor, UNW_REG_IP, &ip);
    backtrace[level] = ip;

    // Print the function name and offset.
    ret = unw_get_proc_name(&cursor, name, sizeof(name), &off);
    if (ret == 0) {
      snprintf(buf, sizeof(buf),
               "%5d 0x%016lx %s() +0x%lx\n",
               level, ip, name, (uintptr_t)off);
    } else {
      snprintf(buf, sizeof(buf),
               "%5d 0x%016lx <unknown>\n",
               level, ip);
    }
    print_str(STDERR_FILENO, buf);
    level++;
    ret = unw_step(&cursor);
    if (ret <= 0)
      break;
  }
  if (ret < 0) {
    print_unw_error("unw_step_ptr", ret);
    return (1);
  }
  return (0);
}

static void segfault_handler(int sig, siginfo_t *info, void *ctx) {
  struct sigaction sa;
  ucontext_t *uap = (ucontext_t*)ctx;
  char buf[64];

  print_str(STDERR_FILENO, "Caught signal ");
  snprintf(buf, sizeof(buf), "%d (", sig);
  print_str(STDERR_FILENO, buf);
  print_str(STDERR_FILENO, strsignal(sig));
  print_str(STDERR_FILENO, ") in process ");
  snprintf(buf, sizeof(buf), "%d, thread %016lx\n", getpid(), pthread_self());
  print_str(STDERR_FILENO, buf);
  print_str(STDERR_FILENO, "\n");

  print_stack_trace(uap);

  // Restore the original signal handler and propagate the signal.
  sigemptyset (&sa.sa_mask);
  sa.sa_handler = SIG_DFL;
  sa.sa_flags = 0;
  sigaction(sig, &sa, NULL);
  kill(getpid(), sig);
}

void stacktrace_init() {
  struct sigaction sa;
  sigemptyset(&sa.sa_mask);
  sa.sa_sigaction = &segfault_handler;
  sa.sa_flags = SA_RESTART | SA_SIGINFO | SA_ONSTACK;

  // Configure the signal handlers.
  sigaction(SIGSEGV, &sa, NULL);
  sigaction(SIGBUS, &sa, NULL);
  sigaction(SIGILL, &sa, NULL);
  sigaction(SIGABRT, &sa, NULL);
  sigaction(SIGFPE, &sa, NULL);
  sigaction(SIGSYS, &sa, NULL);
}

} // namespace noisicaa
