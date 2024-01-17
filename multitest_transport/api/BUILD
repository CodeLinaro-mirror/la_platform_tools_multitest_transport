# MTT API handlers.
load("@tradefed_cluster//tradefed_cluster:adapter.bzl", "py_test", "pytype_strict_library", "third_party")

package(default_applicable_licenses = ["//multitest_transport:license"])

licenses(["notice"])

pytype_strict_library(
    name = "api",
    visibility = ["//multitest_transport"],
    deps = [
        ":server_lib",
    ],
)

pytype_strict_library(
    name = "api_test_util_lib",
    testonly = True,
    srcs = [
        "api_test_util.py",
    ],
    deps = [
        "@tradefed_cluster//tradefed_cluster:testbed_dependent_test_lib",
        third_party("google-endpoints"),
        third_party("webtest"),
    ],
)

pytype_strict_library(
    name = "base_lib",
    srcs = [
        "base.py",
    ],
    deps = [
        ":openapi_lib",
        "//multitest_transport/models",
        "@tradefed_cluster//tradefed_cluster/util:ndb_shim_lib",
        third_party("google-endpoints"),
    ],
)

pytype_strict_library(
    name = "build_api_lib",
    srcs = [
        "build_api.py",
    ],
    deps = [
        ":base_lib",
        "//multitest_transport/build_manager:xts_requirements_detector_lib",
        "//multitest_transport/models",
        "//multitest_transport/test_scheduler:test_kicker_lib",
        "//multitest_transport/util:file_util_lib",
        "@tradefed_cluster//tradefed_cluster/util:ndb_shim_lib",
        third_party("google-endpoints"),
        third_party("protorpc"),
    ],
)

py_test(
    name = "build_api_test",
    srcs = [
        "build_api_test.py",
    ],
    tags = ["not_run:arm"],
    deps = [
        ":api_test_util_lib",
        ":build_api_lib",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
    ],
)

pytype_strict_library(
    name = "build_channel_api_lib",
    srcs = [
        "build_channel_api.py",
    ],
    deps = [
        ":base_lib",
        "//multitest_transport/models",
        "//multitest_transport/util",
        third_party("google/oauth2:service_account"),
        third_party("google-endpoints"),
        third_party("protorpc"),
    ],
)

py_test(
    name = "build_channel_api_test",
    srcs = [
        "build_channel_api_test.py",
    ],
    tags = ["not_run:arm"],
    deps = [
        ":api_test_util_lib",
        ":build_channel_api_lib",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
        third_party("google/oauth2:credentials"),
    ],
)

pytype_strict_library(
    name = "build_channel_provider_api_lib",
    srcs = [
        "build_channel_provider_api.py",
    ],
    deps = [
        ":base_lib",
        "//multitest_transport/models",
        third_party("google-endpoints"),
        third_party("protorpc"),
    ],
)

py_test(
    name = "build_channel_provider_api_test",
    srcs = [
        "build_channel_provider_api_test.py",
    ],
    tags = ["not_run:arm"],
    deps = [
        ":api_test_util_lib",
        ":build_channel_provider_api_lib",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
    ],
)

pytype_strict_library(
    name = "config_set_api_lib",
    srcs = [
        "config_set_api.py",
    ],
    deps = [
        ":base_lib",
        "//multitest_transport/models",
        "//multitest_transport/test_scheduler",
        "//multitest_transport/util",
        third_party("google-endpoints"),
        third_party("protorpc"),
    ],
)

py_test(
    name = "config_set_api_test",
    srcs = [
        "config_set_api_test.py",
    ],
    tags = ["not_run:arm"],
    deps = [
        ":api_test_util_lib",
        ":config_set_api_lib",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
    ],
)

pytype_strict_library(
    name = "device_action_api_lib",
    srcs = [
        "device_action_api.py",
    ],
    deps = [
        ":base_lib",
        "//multitest_transport/models",
        "@tradefed_cluster//tradefed_cluster/util:ndb_shim_lib",
        third_party("google-endpoints"),
        third_party("protorpc"),
    ],
)

pytype_strict_library(
    name = "device_api_lib",
    srcs = [
        "device_api.py",
    ],
    deps = [
        ":base_lib",
        third_party("grpc"),
        "@com_google_deviceinfra//src/devtools/mobileharness/api/model/proto:device_py_pb2",
        "@com_google_deviceinfra//src/devtools/mobileharness/infra/master/rpc/proto:lab_info_service_py_grpc",
        "@com_google_deviceinfra//src/devtools/mobileharness/infra/master/rpc/proto:lab_info_service_py_proto",
        "//multitest_transport/models",
        "//multitest_transport/util:olcs_lab_info_client_lib",
        "@tradefed_cluster//tradefed_cluster:api_messages_lib",
        "@tradefed_cluster//tradefed_cluster/util:ndb_shim_lib",
        third_party("google-endpoints"),
        third_party("protorpc"),
    ],
)

py_test(
    name = "device_api_test",
    srcs = ["device_api_test.py"],
    tags = ["not_run:arm"],
    deps = [
        ":api_test_util_lib",
        ":device_api_lib",
        "@com_google_deviceinfra//src/devtools/mobileharness/api/model/proto:device_py_pb2",
        "@com_google_deviceinfra//src/devtools/mobileharness/infra/master/rpc/proto:lab_info_service_py_proto",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
        "//multitest_transport/util:olcs_lab_info_client_lib",
        third_party("protorpc"),
        "@tradefed_cluster//tradefed_cluster:api_messages_lib",
    ],
)

py_test(
    name = "device_action_api_test",
    srcs = [
        "device_action_api_test.py",
    ],
    tags = ["not_run:arm"],
    deps = [
        ":api_test_util_lib",
        ":device_action_api_lib",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
    ],
)

pytype_strict_library(
    name = "host_api_lib",
    srcs = [
        "host_api.py",
    ],
    deps = [
        ":base_lib",
        ":device_api_lib",
        "@com_google_deviceinfra//src/devtools/mobileharness/api/model/proto:device_py_pb2",
        "@com_google_deviceinfra//src/devtools/mobileharness/infra/master/rpc/proto:lab_info_service_py_proto",
        "//third_party/py/endpoints:endpoints_library",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
        "//multitest_transport/util:olcs_lab_info_client_lib",
        third_party("protorpc"),
        "@tradefed_cluster//tradefed_cluster:api_messages_lib",
    ],
)

py_test(
    name = "host_api_test",
    srcs = [
        "host_api_test.py",
    ],
    tags = ["not_run:arm"],
    deps = [
        ":api_test_util_lib",
        ":base_lib",
        third_party("grpc"),
        ":host_api_lib",
        "@com_google_deviceinfra//src/devtools/mobileharness/api/model/proto:device_py_pb2",
        "@com_google_deviceinfra//src/devtools/mobileharness/infra/master/rpc/proto:lab_info_service_py_grpc",
        "@com_google_deviceinfra//src/devtools/mobileharness/infra/master/rpc/proto:lab_info_service_py_proto",
        "//third_party/py/absl/testing:absltest",
        "//multitest_transport/models",
        "//multitest_transport/util:olcs_lab_info_client_lib",
        "@tradefed_cluster//tradefed_cluster:api_messages_lib",
        "@tradefed_cluster//tradefed_cluster/util:ndb_shim_lib",
        third_party("google-endpoints"),
        third_party("protorpc"),
    ],
)

pytype_strict_library(
    name = "node_config_api_lib",
    srcs = [
        "node_config_api.py",
    ],
    deps = [
        ":base_lib",
        "//multitest_transport/models",
        "//multitest_transport/util",
        third_party("protorpc"),
    ],
)

py_test(
    name = "node_config_api_test",
    srcs = [
        "node_config_api_test.py",
    ],
    tags = ["not_run:arm"],
    deps = [
        ":api_test_util_lib",
        ":node_config_api_lib",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
    ],
)

pytype_strict_library(
    name = "openapi_lib",
    srcs = [
        "openapi.py",
    ],
    deps = [
        third_party("endpoints:openapi_generator"),
    ],
)

pytype_strict_library(
    name = "private_node_config_api_lib",
    srcs = [
        "private_node_config_api.py",
    ],
    deps = [
        ":base_lib",
        "//multitest_transport/models",
        third_party("google/oauth2:service_account"),
        third_party("google-endpoints"),
        third_party("protorpc"),
    ],
)

py_test(
    name = "private_node_config_api_test",
    srcs = [
        "private_node_config_api_test.py",
    ],
    tags = ["not_run:arm"],
    deps = [
        ":api_test_util_lib",
        ":private_node_config_api_lib",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
    ],
)

pytype_strict_library(
    name = "server_lib",
    srcs = [
        "server.py",
    ],
    data = [
        "docs.html",
    ],
    deps = [
        ":base_lib",
        ":build_api_lib",
        ":build_channel_api_lib",
        ":build_channel_provider_api_lib",
        ":config_set_api_lib",
        ":device_action_api_lib",
        ":device_api_lib",
        ":file_cleaner_api_lib",
        ":host_api_lib",
        ":netdata_api_lib",
        ":node_config_api_lib",
        ":openapi_lib",
        ":private_node_config_api_lib",
        ":test_api_lib",
        ":test_plan_api_lib",
        ":test_result_api_lib",
        ":test_run_action_api_lib",
        ":test_run_api_lib",
        "//multitest_transport/util",
        "@tradefed_cluster//tradefed_cluster:api_lib",
        third_party("flask"),
        third_party("google-endpoints"),
    ],
)

pytype_strict_library(
    name = "test_api_lib",
    srcs = [
        "test_api.py",
    ],
    deps = [
        ":base_lib",
        "//multitest_transport/models",
        "@tradefed_cluster//tradefed_cluster/util:ndb_shim_lib",
        third_party("google-endpoints"),
        third_party("protorpc"),
    ],
)

py_test(
    name = "test_api_test",
    srcs = [
        "test_api_test.py",
    ],
    tags = ["not_run:arm"],
    deps = [
        ":api_test_util_lib",
        ":test_api_lib",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
    ],
)

pytype_strict_library(
    name = "test_plan_api_lib",
    srcs = [
        "test_plan_api.py",
    ],
    deps = [
        ":base_lib",
        "//multitest_transport/models",
        "//multitest_transport/test_scheduler",
        "//multitest_transport/test_scheduler:test_kicker_lib",
        "//multitest_transport/test_scheduler:test_plan_kicker_lib",
        "//multitest_transport/util",
        "@tradefed_cluster//tradefed_cluster/util:ndb_shim_lib",
        third_party("croniter"),
        third_party("google-endpoints"),
        third_party("protorpc"),
    ],
)

py_test(
    name = "test_plan_api_test",
    srcs = [
        "test_plan_api_test.py",
    ],
    tags = ["not_run:arm"],
    deps = [
        ":api_test_util_lib",
        ":test_plan_api_lib",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
    ],
)

pytype_strict_library(
    name = "test_result_api_lib",
    srcs = [
        "test_result_api.py",
    ],
    deps = [
        ":base_lib",
        "//multitest_transport/models",
        "//multitest_transport/util",
        third_party("google-endpoints"),
        third_party("protorpc"),
    ],
)

py_test(
    name = "test_result_api_test",
    srcs = [
        "test_result_api_test.py",
    ],
    tags = ["not_run:arm"],
    deps = [
        ":api_test_util_lib",
        ":test_result_api_lib",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
        "//multitest_transport/models",
        "//multitest_transport/util",
        third_party("sqlite3"),
    ],
)

pytype_strict_library(
    name = "test_run_action_api_lib",
    srcs = [
        "test_run_action_api.py",
    ],
    deps = [
        ":base_lib",
        "//multitest_transport/models",
        "//multitest_transport/util",
        "@tradefed_cluster//tradefed_cluster/util:ndb_shim_lib",
        third_party("google/oauth2:service_account"),
        third_party("google-endpoints"),
        third_party("protorpc"),
    ],
)

py_test(
    name = "test_run_action_api_test",
    srcs = [
        "test_run_action_api_test.py",
    ],
    tags = ["not_run:arm"],
    deps = [
        ":api_test_util_lib",
        ":test_run_action_api_lib",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
        third_party("google/oauth2:credentials"),
    ],
)

pytype_strict_library(
    name = "test_run_api_lib",
    srcs = [
        "test_run_api.py",
    ],
    deps = [
        ":base_lib",
        "//multitest_transport/models",
        "//multitest_transport/test_scheduler:test_kicker_lib",
        "//multitest_transport/test_scheduler:test_run_manager_lib",
        "//multitest_transport/util",
        "@tradefed_cluster//tradefed_cluster:common_lib",
        "@tradefed_cluster//tradefed_cluster:datastore_util_lib",
        "@tradefed_cluster//tradefed_cluster/util:ndb_shim_lib",
        third_party("google-endpoints"),
        third_party("protorpc"),
    ],
)

py_test(
    name = "test_run_api_test",
    srcs = [
        "test_run_api_test.py",
    ],
    tags = ["not_run:arm"],
    deps = [
        ":api_test_util_lib",
        ":test_run_api_lib",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
    ],
)

pytype_strict_library(
    name = "file_cleaner_api_lib",
    srcs = [
        "file_cleaner_api.py",
    ],
    deps = [
        ":base_lib",
        "//multitest_transport/models",
        third_party("protorpc"),
    ],
)

py_test(
    name = "file_cleaner_api_test",
    srcs = [
        "file_cleaner_api_test.py",
    ],
    tags = ["not_run:arm"],
    deps = [
        ":api_test_util_lib",
        ":file_cleaner_api_lib",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
    ],
)

pytype_strict_library(
    name = "netdata_api_lib",
    srcs = [
        "netdata_api.py",
    ],
    deps = [
        ":base_lib",
        "//multitest_transport/models",
        "//multitest_transport/util",
        third_party("google-endpoints"),
        third_party("protorpc"),
        third_party("requests"),
    ],
)

py_test(
    name = "netdata_api_test",
    srcs = [
        "netdata_api_test.py",
    ],
    tags = ["not_run:arm"],
    deps = [
        ":api_test_util_lib",
        ":netdata_api_lib",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
        third_party("requests_mock"),
    ],
)
