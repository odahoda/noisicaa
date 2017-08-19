add_python_package(
  csound_test.py
  fluidsynth_test.py
  sndfile_test.py
  sratom_test.py
)

add_cython_module(fluidsynth C)
target_include_directories(${fluidsynth.so} PRIVATE ${LIBFLUIDSYNTH_INCLUDE_DIRS})
target_link_libraries(${fluidsynth.so} PRIVATE ${LIBFLUIDSYNTH_LIBRARIES})

add_cython_module(csound C)
target_include_directories(${csound.so} PRIVATE ${LIBCSOUND_INCLUDE_DIRS})
target_link_libraries(${csound.so} PRIVATE ${LIBCSOUND_LIBRARIES})

add_cython_module(ladspa C)

add_cython_module(lilv C)
target_include_directories(${lilv.so} PRIVATE ${LIBLILV_INCLUDE_DIRS})
target_link_libraries(${lilv.so} PRIVATE ${LIBLILV_LIBRARIES})

add_cython_module(sndfile C)
target_include_directories(${sndfile.so} PRIVATE ${LIBSNDFILE_INCLUDE_DIRS})
target_link_libraries(${sndfile.so} PRIVATE ${LIBSNDFILE_LIBRARIES})

add_cython_module(sratom C)
target_include_directories(${sratom.so} PRIVATE ${LIBSRATOM_INCLUDE_DIRS})
target_link_libraries(${sratom.so} PRIVATE ${LIBSRATOM_LIBRARIES})


add_subdirectory(lv2)
