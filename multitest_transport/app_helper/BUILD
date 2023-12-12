# Helpers for off-cloud environment.
load("@tradefed_cluster//tradefed_cluster:adapter.bzl", "py_test", "pytype_strict_library", "third_party")

package(
    default_applicable_licenses = ["//multitest_transport:license"],
    default_visibility = ["//multitest_transport"],
)

licenses(["notice"])

pytype_strict_library(
    name = "launcher_lib",
    srcs = [
        "launcher.py",
    ],
    deps = [
        ":rabbitmq_plugin_lib",
        "//third_party/py/google/appengine/api:full_app_id",
        "//multitest_transport/models:test_run_hook_lib",
        "@tradefed_cluster//tradefed_cluster:common_lib",
        "@tradefed_cluster//tradefed_cluster:env_config_lib",
        "@tradefed_cluster//tradefed_cluster/plugins:base_lib",
        "@tradefed_cluster//tradefed_cluster/util:ndb_shim_lib",
        third_party("absl:app"),
        third_party("absl/flags"),
        third_party("attr"),
        third_party("gunicorn"),
        third_party("requests"),
    ],
)

py_test(
    name = "launcher_test",
    srcs = [
        "launcher_test.py",
    ],
    deps = [
        ":launcher_lib",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
        third_party("absl/testing:absltest"),
        third_party("absl/testing:parameterized"),
    ],
)

pytype_strict_library(
    name = "rabbitmq_plugin_lib",
    srcs = [
        "rabbitmq_plugin.py",
    ],
    deps = [
        "@tradefed_cluster//tradefed_cluster/plugins:base_lib",
        third_party("pika"),
        third_party("pytz"),
    ],
)

py_test(
    name = "rabbitmq_plugin_test",
    srcs = [
        "rabbitmq_plugin_test.py",
    ],
    deps = [
        ":rabbitmq_plugin_lib",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
        third_party("absl/testing:absltest"),
    ],
)

pytype_strict_library(
    name = "rabbitmq_puller_lib",
    srcs = [
        "rabbitmq_puller.py",
    ],
    deps = [
        third_party("absl:app"),
        third_party("absl/flags"),
        third_party("pika"),
        third_party("yaml"),
    ],
)

py_test(
    name = "rabbitmq_puller_test",
    srcs = [
        "rabbitmq_puller_test.py",
    ],
    deps = [
        ":rabbitmq_puller_lib",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
        third_party("absl/testing:absltest"),
    ],
)
