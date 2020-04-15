import os

from conans import ConanFile, CMake, tools
from conans.errors import ConanInvalidConfiguration

class GlslangConan(ConanFile):
    name = "glslang"
    description = "Khronos-reference front end for GLSL/ESSL, partial front " \
                  "end for HLSL, and a SPIR-V generator."
    license = ["BSD-3-Clause", "NVIDIA"]
    topics = ("conan", "glslang", "glsl", "hlsl", "spirv", "spir-v", "validation", "translation")
    homepage = "https://github.com/KhronosGroup/glslang"
    url = "https://github.com/conan-io/conan-center-index"
    exports_sources = "CMakeLists.txt"
    generators = "cmake"
    settings = "os", "arch", "compiler", "build_type"
    options = {
        "shared": [True, False],
        "fPIC": [True, False],
        "build_executables": [True, False],
        "SPVRemapper": [True, False],
        "hlsl": [True, False],
        "with_spirv_tools": [True, False]
    }
    default_options = {
        "shared": False,
        "fPIC": True,
        "build_executables": True,
        "SPVRemapper": True,
        "hlsl": True,
        "with_spirv_tools": False
    }

    _cmake = None

    @property
    def _source_subfolder(self):
        return "source_subfolder"

    @property
    def _build_subfolder(self):
        return "build_subfolder"

    def config_options(self):
        if self.settings.os == "Windows":
            del self.options.fPIC

    def configure(self):
        if self.settings.compiler.cppstd:
            tools.check_min_cppstd(self, 11)
        if self.options.shared and self.settings.os in ["Windows", "Macos"]:
            raise ConanInvalidConfiguration("Current glslang shared library build is broken on Windows and Macos")

    def requirements(self):
        if self.options.with_spirv_tools:
            raise ConanInvalidConfiguration("spirv-tools not yet available in conan-center-index")
            self.requires.add("spirv-tools/2020.1")

    def source(self):
        tools.get(**self.conan_data["sources"][self.version])
        os.rename(self.name + "-" + self.version, self._source_subfolder)

    def build(self):
        self._patches_sources()
        cmake = self._configure_cmake()
        cmake.build()

    def _patches_sources(self):
        # Do not force PIC
        cmake_files_to_fix = [
            {"target": "OGLCompiler", "relpath": os.path.join("OGLCompilersDLL", "CMakeLists.txt")},
            {"target": "SPIRV"      , "relpath": os.path.join("SPIRV", "CMakeLists.txt")},
            {"target": "SPVRemapper", "relpath": os.path.join("SPIRV", "CMakeLists.txt")},
            {"target": "glslang"    , "relpath": os.path.join("glslang", "CMakeLists.txt")},
            {"target": "OSDependent", "relpath": os.path.join("glslang", "OSDependent", "Unix","CMakeLists.txt")},
            {"target": "OSDependent", "relpath": os.path.join("glslang", "OSDependent", "Windows","CMakeLists.txt")},
            {"target": "HLSL"       , "relpath": os.path.join("hlsl", "CMakeLists.txt")},
        ]
        for cmake_file in cmake_files_to_fix:
            tools.replace_in_file(os.path.join(self._source_subfolder, cmake_file["relpath"]),
                                  "set_property(TARGET {} PROPERTY POSITION_INDEPENDENT_CODE ON)".format(cmake_file["target"]),
                                  "")

    def _configure_cmake(self):
        if self._cmake:
            return self._cmake
        self._cmake = CMake(self)
        self._cmake.definitions["BUILD_EXTERNAL"] = False
        self._cmake.definitions["SKIP_GLSLANG_INSTALL"] = False
        self._cmake.definitions["ENABLE_SPVREMAPPER"] = self.options.SPVRemapper
        self._cmake.definitions["ENABLE_GLSLANG_BINARIES"] = self.options.build_executables
        self._cmake.definitions["ENABLE_GLSLANG_WEB"] = False
        self._cmake.definitions["ENABLE_GLSLANG_WEB_DEVEL"] = False
        self._cmake.definitions["ENABLE_EMSCRIPTEN_SINGLE_FILE"] = False
        self._cmake.definitions["ENABLE_EMSCRIPTEN_ENVIRONMENT_NODE"] = False
        self._cmake.definitions["ENABLE_HLSL"] = self.options.hlsl
        self._cmake.definitions["ENABLE_OPT"] = self.options.with_spirv_tools
        self._cmake.definitions["ENABLE_PCH"] = True
        self._cmake.definitions["ENABLE_CTEST"] = False
        self._cmake.definitions["USE_CCACHE"] = False
        self._cmake.configure(build_folder=self._build_subfolder)
        return self._cmake

    def package(self):
        self.copy("LICENSE.txt", dst="licenses", src=self._source_subfolder)
        cmake = self._configure_cmake()
        cmake.install()
        tools.rmdir(os.path.join(self.package_folder, "lib", "cmake"))

    def package_info(self):
        # CMake Targets: SPIRV, glslang, OGLCompiler, OSDependent, SPVRemapper, HLSL
        # To update when conan components available
        self.cpp_info.names["cmake_find_package"] = "glslang"
        self.cpp_info.names["cmake_find_package_multi"] = "glslang"
        self.cpp_info.libs = self._get_ordered_libs()
        if self.settings.os == "Linux":
            self.cpp_info.system_libs.append("pthread") # for OSDependent
        if self.options.build_executables:
            self.env_info.PATH.append(os.path.join(self.package_folder, "bin"))

    def _get_ordered_libs(self):
        # - SPIRV depends on glslang if with_spirv_tools if False
        # - glslang depends on OGLCompiler and OSDependent (and HLSL if ENABLE_HLSL)
        libs = ["SPIRV", "glslang", "OGLCompiler", "OSDependent"]
        if self.options.SPVRemapper:
            libs.append("SPVRemapper")
        if self.options.hlsl:
            libs.append("HLSL")
        if self.settings.os == "Windows" and self.settings.build_type == "Debug":
            libs = [lib + "d" for lib in libs]
        return libs
