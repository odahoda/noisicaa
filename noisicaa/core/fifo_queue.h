// -*- mode: c++ -*-

/*
 * @custom_license
 *
 * Based on https://bitbucket.org/KjellKod/lock-free-wait-free-circularfifo
 * with local modifications.
 *
 * Not any company's property but Public-Domain
 * Do with source-code as you will. No requirement to keep this
 * header if need to use it/change it/ or do whatever with it
 *
 * Note that there is No guarantee that this code will work
 * and I take no responsibility for this code and any problems you
 * might get if using it.
 *
 * Code & platform dependent issues with it was originally
 * published at http://www.kjellkod.cc/threadsafecircularqueue
 * 2012-16-19  @author Kjell Hedström, hedstrom@kjellkod.cc
 */

#ifndef _NOISICAA_CORE_QUEUE_H
#define _NOISICAA_CORE_QUEUE_H

#include <atomic>
#include <cstddef>

namespace noisicaa {

using namespace std;

template<typename Element, size_t Size>
class FifoQueue {
public:
  enum { Capacity = Size + 1 };

  FifoQueue() : _tail(0), _head(0) {}
  virtual ~FifoQueue() {}

  bool push(const Element& item);
  bool pop(Element& item);

  bool wasEmpty() const;
  bool wasFull() const;
  bool isLockFree() const;

private:
  size_t increment(size_t idx) const;

  std::atomic<size_t> _tail;
  Element _array[Capacity];
  std::atomic<size_t> _head;
};

template<typename Element, size_t Size>
bool FifoQueue<Element, Size>::push(const Element& item) {
  const auto current_tail = _tail.load(std::memory_order_relaxed);
  const auto next_tail = increment(current_tail);
  if (next_tail != _head.load(std::memory_order_acquire)) {
    _array[current_tail] = item;
    _tail.store(next_tail, std::memory_order_release);
    return true;
  }

  // full queue
  return false;
}

// Pop by Consumer can only update the head (load with relaxed, store with release)
//     the tail must be accessed with at least aquire
template<typename Element, size_t Size>
bool FifoQueue<Element, Size>::pop(Element& item) {
  const auto current_head = _head.load(std::memory_order_relaxed);
  if (current_head == _tail.load(std::memory_order_acquire)) {
    // empty queue
    return false;
  }

  item = _array[current_head];
  _head.store(increment(current_head), std::memory_order_release);
  return true;
}

template<typename Element, size_t Size>
bool FifoQueue<Element, Size>::wasEmpty() const {
  // snapshot with acceptance of that this comparison operation is not atomic
  return _head.load() == _tail.load();
}

// snapshot with acceptance that this comparison is not atomic
template<typename Element, size_t Size>
bool FifoQueue<Element, Size>::wasFull() const {
  const auto next_tail = increment(_tail.load()); // aquire, we don't know who call
  return next_tail == _head.load();
}

template<typename Element, size_t Size>
bool FifoQueue<Element, Size>::isLockFree() const {
  return _tail.is_lock_free() && _head.is_lock_free();
}

template<typename Element, size_t Size>
size_t FifoQueue<Element, Size>::increment(size_t idx) const {
  return (idx + 1) % Capacity;
}

}  // namespace noisicaa

#endif
