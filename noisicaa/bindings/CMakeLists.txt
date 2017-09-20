add_python_package(
  sndfile_test.py
  sratom_test.py
)

add_cython_module(ladspa CXX)

add_cython_module(lilv CXX)
target_include_directories(${lilv.so} PRIVATE ${LIBLILV_INCLUDE_DIRS})
target_link_libraries(${lilv.so} PRIVATE ${LIBLILV_LIBRARIES})

add_cython_module(sndfile CXX)
target_include_directories(${sndfile.so} PRIVATE ${LIBSNDFILE_INCLUDE_DIRS})
target_link_libraries(${sndfile.so} PRIVATE ${LIBSNDFILE_LIBRARIES})

add_cython_module(sratom CXX)
target_include_directories(${sratom.so} PRIVATE ${LIBSRATOM_INCLUDE_DIRS})
target_link_libraries(${sratom.so} PRIVATE ${LIBSRATOM_LIBRARIES})

file(COPY testdata DESTINATION .)

add_subdirectory(lv2)
