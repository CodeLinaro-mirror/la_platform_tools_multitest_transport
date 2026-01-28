# MTT integration tests.

load("@tradefed_cluster//tradefed_cluster:adapter.bzl", "py_library", "py_test", "third_party")

package(default_applicable_licenses = ["//multitest_transport:license"])

licenses(["notice"])

py_library(
    name = "integration_util",
    testonly = True,
    srcs = [
        "integration_util.py",
    ],
    data = [
        "//multitest_transport/cli:seccomp.json",
    ],
    strict_deps = False,
    deps = [
        third_party("absl/testing:absltest"),
        third_party("docker"),
        third_party("portpicker"),
        third_party("requests"),
        third_party("retry"),
        "//third_party/py/absl/flags",
    ],
)

py_test(
    name = "base_integration_test",
    srcs = [
        "base_integration_test.py",
    ],
    features = ["-enable_relr"],
    linking_mode = "static",
    tags = ["local"],
    deps = [
        ":integration_util",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
    ],
)

# Run with blaze test integration_test:e2e_test --test_arg="--docker_image=<image to test>" --test_arg="--serial_number=<device to test>" --cache_test_results=no --flaky_test_attempts=3
py_test(
    name = "e2e_test",
    timeout = "eternal",
    srcs = [
        "e2e_test.py",
    ],
    data = [
        "test_data/android-cts-git_24Q3-release-test_suites_x86_64-11835886-trimmed.zip",
        "test_data/e2e_test_config.yaml",
    ],
    features = ["-enable_relr"],
    linking_mode = "static",
    tags = ["local"],
    deps = [
        ":integration_util",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
    ],
)

py_test(
    name = "ats2_e2e_test",
    timeout = "eternal",
    srcs = [
        "ats2_e2e_test.py",
    ],
    data = [
        "test_data/android-cts-git_24Q3-release-test_suites_x86_64-11835886-trimmed.zip",
        "test_data/e2e_test_config.yaml",
    ],
    features = ["-enable_relr"],
    linking_mode = "static",
    tags = ["local"],
    deps = [
        ":integration_util",
        "//third_party/py/absl/flags",
        "//third_party/py/absl/testing:absltest",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
    ],
)

# Run with blaze test //multitest_transport/integration_test:ats2_e2e_local_validation_test \
#   --test_arg=--serial_number=<device_serial> \
#   --test_arg=--container_id=mtt \
#   --test_output=streamed \
#   --test_arg=--xts_file=<local_cts_zip_path>
#   --cache_test_results=no
py_test(
    name = "ats2_e2e_local_validation_test",
    timeout = "eternal",
    srcs = [
        "ats2_e2e_local_validation_test.py",
    ],
    data = [
        "test_data/e2e_test_config.yaml",
    ],
    features = ["-enable_relr"],
    linking_mode = "static",
    tags = ["local"],
    deps = [
        ":integration_util",
        "//third_party/py/absl/flags",
        "//third_party/py/absl/testing:absltest",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
    ],
)

py_test(
    name = "event_handler_integration_test",
    srcs = [
        "event_handler_integration_test.py",
    ],
    features = ["-enable_relr"],
    linking_mode = "static",
    shard_count = 2,
    tags = ["local"],
    deps = [
        ":integration_util",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
    ],
)

py_test(
    name = "file_server_integration_test",
    srcs = [
        "file_server_integration_test.py",
    ],
    data = [
        "test_data/android-cts.zip",
        "test_data/stdout.txt",
        "test_data/test_result.xml",
    ],
    features = ["-enable_relr"],
    linking_mode = "static",
    tags = ["local"],
    deps = [
        ":integration_util",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
    ],
)

py_test(
    name = "test_scheduler_integration_test",
    srcs = [
        "test_scheduler_integration_test.py",
    ],
    features = ["-enable_relr"],
    linking_mode = "static",
    tags = ["local"],
    deps = [
        ":integration_util",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
    ],
)

# Run with blaze test integration_test:image_tests --test_arg="--docker_image=<image to test>" --cache_test_results=no --flaky_test_attempts=3
test_suite(
    name = "image_tests",
    tests = [
        ":base_integration_test",
        ":event_handler_integration_test",
        ":file_server_integration_test",
        ":test_scheduler_integration_test",
    ],
)

# Combination of all integration tests for CI
test_suite(
    name = "integration_test",
    tests = [
        ":ats2_e2e_test",
        ":e2e_test",
        ":image_tests",
        "//multitest_transport/cli:integration_test",
    ],
)
