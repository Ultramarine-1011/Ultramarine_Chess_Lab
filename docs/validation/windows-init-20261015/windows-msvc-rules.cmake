# Local workaround for CMake decoding this host's UTF-8 cl output as CP936.
# Only replace the exact mojibake prefix observed on this installation.
if(MSVC AND CMAKE_CL_SHOWINCLUDES_PREFIX STREQUAL "娉ㄦ剰: 鍖呭惈鏂囦欢:  ")
  set(CMAKE_CL_SHOWINCLUDES_PREFIX "注意: 包含文件:  ")
endif()
