# MTT Command Line Interfaces
load("@tradefed_cluster//tradefed_cluster:adapter.bzl", "Fileset", "FilesetEntry", "py_library", "py_test", "pytype_strict_binary", "third_party", "zip_dir")

package(default_applicable_licenses = ["//multitest_transport:license"])

licenses(["notice"])

exports_files(["seccomp.json"])

pytype_strict_binary(
    name = "cli",
    srcs = ["cli.py"],
    test_lib = True,
    visibility = ["//visibility:private"],
    deps = [":cli_lib"],
)

py_library(
    name = "cli_lib",
    srcs = [
        "cli.py",
    ],
    data = [
        "seccomp.json",
    ],
    deps = [
        ":cli_util_lib",
        ":command_util_lib",
        ":google_auth_util_lib",
        ":host_util_lib",
        ":ssh_util_lib",
        "@tradefed_cluster//tradefed_cluster/configs:lab_config_py_pb2",
        third_party("packaging"),
        third_party("six"),
    ],
)

py_library(
    name = "cli_util_lib",
    srcs = [
        "cli_util.py",
    ],
    deps = [
        ":command_util_lib",
        ":gcs_file_util_lib",
        ":google_auth_util_lib",
        ":version_data_lib",
        third_party("google/cloud/logging"),
        third_party("requests"),
        third_party("six"),
    ],
)

py_library(
    name = "cluster_lib",
    srcs = [
        "cluster.py",
    ],
    deps = [
        ":command_util_lib",
    ],
)

py_library(
    name = "command_util_lib",
    srcs = [
        "command_util.py",
    ],
    deps = [
        ":common",
        ":google_auth_util_lib",
        ":ssh_util_lib",
        third_party("six"),
    ],
)

py_library(
    name = "common",
    srcs = [
        "common.py",
    ],
)

py_library(
    name = "gcs_file_util_lib",
    srcs = [
        "gcs_file_util.py",
    ],
    deps = [
        third_party("google/cloud/storage"),
    ],
)

py_library(
    name = "google_auth_util_lib",
    srcs = [
        "google_auth_util.py",
    ],
    deps = [
        third_party("apiclient"),
        third_party("google/auth:transport/requests"),
        third_party("google/oauth2:credentials"),
        third_party("google/oauth2:service_account"),
        third_party("google/cloud/secretmanager"),
    ],
)

pytype_strict_binary(
    name = "lab_cli",
    srcs = ["lab_cli.py"],
    test_lib = True,
    deps = [
        ":lab_cli_lib",
        third_party("dateutil"),
    ],
)

py_library(
    name = "lab_cli_lib",
    srcs = [
        "lab_cli.py",
    ],
    deps = [
        ":cli_util_lib",
        ":command_util_lib",
        ":google_auth_util_lib",
        ":host_util_lib",
    ],
)

py_library(
    name = "host_util_lib",
    srcs = [
        "host_util.py",
    ],
    deps = [
        ":command_util_lib",
        ":control_server_util_lib",
        ":gcs_file_util_lib",
        ":google_auth_util_lib",
        ":ssh_util_lib",
        "@tradefed_cluster//tradefed_cluster/configs:lab_config_lib",
    ],
)

py_library(
    name = "control_server_util_lib",
    srcs = [
        "control_server_util.py",
    ],
    deps = [
        ":google_auth_util_lib",
        "@tradefed_cluster//tradefed_cluster/configs:lab_config_lib",
        third_party("apiclient"),
        third_party("google_auth_httplib2"),
        third_party("pytz"),
    ],
)

py_library(
    name = "ssh_util_lib",
    srcs = [
        "ssh_util.py",
    ],
    deps = [
        ":common",
        third_party("attr"),
    ],
)

py_library(
    name = "unittest_util_lib",
    testonly = 1,
    srcs = [
        "unittest_util.py",
    ],
    deps = [
        third_party("six"),
    ],
)

py_library(
    name = "version_data_lib",
    srcs = [
        "version.py",
    ],
)

# Test

py_test(
    name = "cli_test",
    srcs = [
        "cli_test.py",
    ],
    deps = [
        ":cli_lib",
        ":cli_util_lib",
        ":command_util_lib",
        ":common",
        ":google_auth_util_lib",
        ":unittest_util_lib",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
        "@tradefed_cluster//tradefed_cluster/configs:lab_config_lib",
        third_party("absl/testing:absltest"),
        third_party("absl/testing:parameterized"),
    ],
)

py_test(
    name = "cli_util_test",
    srcs = [
        "cli_util_test.py",
    ],
    deps = [
        ":cli_util_lib",
        ":unittest_util_lib",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
        third_party("absl/testing:absltest"),
        third_party("absl/testing:parameterized"),
    ],
)

py_test(
    name = "command_util_test",
    srcs = [
        "command_util_test.py",
    ],
    deps = [
        ":command_util_lib",
        ":ssh_util_lib",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
        third_party("absl/testing:absltest"),
    ],
)

py_test(
    name = "gcs_file_util_test",
    srcs = [
        "gcs_file_util_test.py",
    ],
    deps = [
        ":gcs_file_util_lib",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
        "@tradefed_cluster//tradefed_cluster/configs:lab_config_lib",
        third_party("absl/testing:absltest"),
    ],
)

py_test(
    name = "google_auth_util_test",
    srcs = [
        "google_auth_util_test.py",
    ],
    deps = [
        ":google_auth_util_lib",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
        third_party("absl/testing:absltest"),
    ],
)

py_test(
    name = "host_util_test",
    srcs = [
        "host_util_test.py",
    ],
    deps = [
        ":host_util_lib",
        ":ssh_util_lib",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
        third_party("absl/testing:absltest"),
        third_party("absl/testing:parameterized"),
    ],
)

py_test(
    name = "control_server_util_test",
    srcs = [
        "control_server_util_test.py",
    ],
    deps = [
        ":control_server_util_lib",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
        third_party("apiclient"),
        third_party("absl/testing:absltest"),
    ],
)

py_test(
    name = "lab_cli_test",
    srcs = [
        "lab_cli_test.py",
    ],
    deps = [
        ":lab_cli_lib",
        ":unittest_util_lib",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
        "@tradefed_cluster//tradefed_cluster/configs:lab_config_lib",
        third_party("absl/testing:absltest"),
        third_party("absl/testing:parameterized"),
    ],
)

py_test(
    name = "ssh_util_test",
    srcs = [
        "ssh_util_test.py",
    ],
    deps = [
        ":ssh_util_lib",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
        third_party("absl/testing:absltest"),
        third_party("absl/testing:parameterized"),
    ],
)

# Run with blaze test cli:integration_test --test_arg=...
py_test(
    name = "integration_test",
    srcs = [
        "integration_test.py",
    ],
    tags = ["local"],
    deps = [
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
        third_party("absl/testing:absltest"),
        # TODO: remove six
        third_party("six"),
    ],
)

