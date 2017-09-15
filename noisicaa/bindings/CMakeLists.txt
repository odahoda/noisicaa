add_python_package(
  sndfile_test.py
  sratom_test.py
)

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
