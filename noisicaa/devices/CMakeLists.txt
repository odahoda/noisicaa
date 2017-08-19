add_python_package(
  libalsa_test.py
  midi_events.py
  midi_hub.py
  midi_hub_test.py
)

add_cython_module(libalsa C)
target_link_libraries(${libalsa.so} PRIVATE asound)
