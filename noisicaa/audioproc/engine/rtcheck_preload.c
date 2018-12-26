/*
 * @begin:license
 *
 * Copyright (c) 2015-2018, Benjamin Niemann <pink@odahoda.de>
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License along
 * with this program; if not, write to the Free Software Foundation, Inc.,
 * 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
 *
 * @end:license
 */

#define _GNU_SOURCE

#include <assert.h>
#include <stdlib.h>
#include <dlfcn.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/syscall.h>
#include "rtcheck.h"


void __rtcheck_violation() {
  rt_checker_violation_found();

  char* e = getenv("RTCHECK_ABORT");
  if (e != NULL && strlen(e) > 0) {
    abort();
  }
}

void* malloc(size_t size) {
  typedef void* (*malloc_t)(size_t);
  static malloc_t real = NULL;
  static int recurse = 0;

  if (recurse) {
    if (real == NULL) {
      fprintf(stderr, "Recursive malloc() during init!\n");
      exit(1);
    }
    return real(size);
  }

  recurse = 1;

  if (real == NULL) {
    *(void**)(&real) = dlsym(RTLD_NEXT, "malloc");
    if (real == NULL) {
      fprintf(stderr, "Oops, no malloc()\n");
      exit(1);
    }
  }

  void *alloc = real(size);

  if (rt_checker_enabled()) {
    fprintf(stderr, "%d %ld: malloc(%lu) = %p\n", getpid(), syscall(__NR_gettid), size, alloc);
    __rtcheck_violation();
  }

  recurse = 0;
  return alloc;
}

void free(void* alloc) {
  typedef void (*free_t)(void*);
  static free_t real = NULL;
  static int recurse = 0;

  if (recurse) {
    if (real == NULL) {
      fprintf(stderr, "Recursive free() during init!\n");
      exit(1);
    }
    real(alloc);
    return;
  }

  recurse = 1;

  if (real == NULL) {
    *(void**)(&real) = dlsym(RTLD_NEXT, "free");
    if (real == NULL) {
      fprintf(stderr, "Oops, no free()\n");
      exit(1);
    }
  }

  real(alloc);

  if (rt_checker_enabled()) {
    fprintf(stderr, "%d %ld: free(%p)\n", getpid(), syscall(__NR_gettid), alloc);
    __rtcheck_violation();
  }

  recurse = 0;
}
