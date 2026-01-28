load("@tradefed_cluster//tradefed_cluster:adapter.bzl", "py_library", "py_test", "pytype_strict_library", "third_party")

package(
    default_applicable_licenses = ["//multitest_transport:license"],
    default_visibility = ["//multitest_transport"],
)

licenses(["notice"])

exports_files(
    [
        "env.py",
        "util.py",
        "worker_lab_health_client.py",
        "channel_util.py",
    ],
)

pytype_strict_library(
    name = "util_lib",
    srcs = [
        "util.py",
    ],
    deps = [],
)

py_test(
    name = "util_test",
    srcs = [
        "util_test.py",
    ],
    deps = [
        ":util_lib",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
        third_party("absl/testing:absltest"),
    ],
)

pytype_strict_library(
    name = "analytics_lib",
    srcs = [
        "analytics.py",
    ],
    deps = [
        ":env_lib",
        ":tfc_client_lib",
        "@tradefed_cluster//tradefed_cluster:common_lib",
        "@tradefed_cluster//tradefed_cluster/services:task_scheduler_lib",
    ],
)

py_test(
    name = "analytics_test",
    srcs = [
        "analytics_test.py",
    ],
    deps = [
        ":analytics_lib",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
        third_party("absl/testing:absltest"),
    ],
)

pytype_strict_library(
    name = "analytics_uploader_lib",
    srcs = [
        "analytics_uploader.py",
    ],
    visibility = ["//multitest_transport"],
    deps = [
        ":util",
        "//multitest_transport/models",
        third_party("flask"),
    ],
)

py_test(
    name = "analytics_uploader_test",
    srcs = [
        "analytics_uploader_test.py",
    ],
    tags = ["not_run:arm"],
    deps = [
        ":analytics_uploader_lib",
        ":env_lib",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
        "//multitest_transport/models:ndb_models_lib",
        "@tradefed_cluster//tradefed_cluster:testbed_dependent_test_lib",
        third_party("absl/testing:absltest"),
    ],
)

pytype_strict_library(
    name = "apfe_client_lib",
    srcs = [
        "apfe_client.py",
    ],
    deps = [
        ":constant_lib",
        ":file_util_lib",
        ":oauth2_util_lib",
        "//multitest_transport/models:ndb_models_lib",
        "//third_party/py/protorpc:protorpc_all",
        "@tradefed_cluster//tradefed_cluster/util:ndb_shim_lib",
        third_party("apiclient"),
        third_party("httplib2"),
    ],
)

py_test(
    name = "apfe_client_test",
    srcs = [
        "apfe_client_test.py",
    ],
    tags = ["not_run:arm"],
    deps = [
        ":apfe_client_lib",
        "@tradefed_cluster//tradefed_cluster:testbed_dependent_test_lib",
        "@tradefed_cluster//tradefed_cluster/util:ndb_shim_lib",
        third_party("absl/testing:absltest"),
        third_party("google/protobuf:use_fast_cpp_protos"),
    ],
)

pytype_strict_library(
    name = "constant_lib",
    srcs = [
        "constant.py",
    ],
)

pytype_strict_library(
    name = "env_lib",
    srcs = [
        "env.py",
    ],
    deps = ["//third_party/py/google/appengine/api:full_app_id"],
)

pytype_strict_library(
    name = "errors_lib",
    srcs = [
        "errors.py",
    ],
)

pytype_strict_library(
    name = "oauth2_util_lib",
    srcs = [
        "oauth2_util.py",
    ],
    deps = [
        "@tradefed_cluster//tradefed_cluster/util:ndb_shim_lib",
        third_party("google/auth:credentials"),
        third_party("google/oauth2:credentials"),
        third_party("google_auth_httplib2"),
        third_party("google_auth_oauthlib"),
        third_party("httplib2"),
    ],
)

py_test(
    name = "oauth2_util_test",
    srcs = [
        "oauth2_util_test.py",
    ],
    tags = ["not_run:arm"],
    deps = [
        ":oauth2_util_lib",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
        "@tradefed_cluster//tradefed_cluster:testbed_dependent_test_lib",
        third_party("google/oauth2:service_account"),
    ],
)

# Use py_library as sqlalchemy imports don't work with pytype_strict_library
py_library(
    name = "sql_util_lib",
    srcs = ["sql_util.py"],
    strict_deps = False,
    deps = [
        third_party("protorpc"),
        third_party("sqlalchemy"),
        third_party("sqlalchemy_utils"),
    ],
)

py_test(
    name = "sql_util_test",
    srcs = [
        "sql_util_test.py",
    ],
    deps = [
        ":sql_util_lib",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
        third_party("absl/testing:absltest"),
        third_party("protorpc"),
        third_party("sqlalchemy"),
        third_party("sqlalchemy_utils"),
        third_party("sqlite3"),
    ],
)

pytype_strict_library(
    name = "tfc_client_lib",
    srcs = [
        "tfc_client.py",
    ],
    deps = [
        ":env_lib",
        ":olcs_lab_info_stub",
        ":olcs_session_stub",
        "@tradefed_cluster//tradefed_cluster:api_messages_lib",
        "@tradefed_cluster//tradefed_cluster:common_lib",
        "@tradefed_cluster//tradefed_cluster/services:app_manager_lib",
        "@tradefed_cluster//tradefed_cluster/util:ndb_shim_lib",
        third_party("apiclient"),
        third_party("httplib2"),
        third_party("protorpc"),
        third_party("requests"),
    ],
)

py_test(
    name = "tfc_client_test",
    srcs = [
        "tfc_client_test.py",
    ],
    tags = ["not_run:arm"],
    deps = [
        ":olcs_lab_info_stub",
        ":tfc_client_lib",
        "//third_party/py/apiclient",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
        "@tradefed_cluster//tradefed_cluster:api_messages_lib",
        "@tradefed_cluster//tradefed_cluster:testbed_dependent_test_lib",
        "@tradefed_cluster//tradefed_cluster/plugins:base_lib",
        third_party("absl/testing:absltest"),
    ],
)

pytype_strict_library(
    name = "util",
    visibility = ["//multitest_transport"],
    deps = [
        ":analytics_lib",
        ":constant_lib",
        ":env_lib",
        ":errors_lib",
        ":file_util_lib",
        ":oauth2_util_lib",
        ":sql_util_lib",
        ":tfc_client_lib",
        ":xts_result_lib",
    ],
)

pytype_strict_library(
    name = "file_util_lib",
    srcs = [
        "file_util.py",
    ],
    deps = [
        ":env_lib",
        third_party("apiclient"),
    ],
)

py_test(
    name = "file_util_test",
    srcs = [
        "file_util_test.py",
    ],
    data = [
        "test_data/FILES",
        "test_data/test_package.zip",
        "test_data/test_package-empty.zip",
        "test_data/test_package-invalid.zip",
        "test_data/test_result.xml",
    ],
    deps = [
        ":env_lib",
        ":file_util_lib",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
        third_party("absl/testing:absltest"),
        third_party("absl/testing:parameterized"),
    ],
)

pytype_strict_library(
    name = "xts_result_lib",
    srcs = [
        "xts_result.py",
    ],
    deps = [
        third_party("attr"),
        third_party("defusedxml"),
        third_party("protorpc"),
    ],
)

py_test(
    name = "olcs_session_stub_test",
    srcs = [
        "olcs_session_stub_test.py",
    ],
    data = [
        "test_data/request_detail.textproto",
        "test_data/test_new_request_msg.json",
    ],
    deps = [
        ":olcs_session_client_lib",
        third_party("absl/testing:absltest"),
        ":olcs_session_stub",
        "//net/grpc/python:grpc",
        "@com_google_deviceinfra//src/devtools/mobileharness/infra/ats/server/proto:service_py_proto",
        "@com_google_deviceinfra//src/devtools/mobileharness/infra/client/longrunningservice/proto:session_py_proto",
        "@com_google_deviceinfra//src/devtools/mobileharness/infra/client/longrunningservice/proto:session_service_py_grpc",
        "@com_google_deviceinfra//src/devtools/mobileharness/infra/client/longrunningservice/proto:session_service_py_proto",
        third_party("protorpc"),
        "//third_party/py/google/protobuf",
        "//third_party/py/grpc_testing",
        "//multitest_transport/models:ndb_models_lib",
        "@tradefed_cluster//tradefed_cluster:api_messages_lib",
        "@tradefed_cluster//tradefed_cluster:testbed_dependent_test_lib",
        "@tradefed_cluster//tradefed_cluster/util:ndb_shim_lib",
        "@tradefed_cluster//tradefed_cluster/util:ndb_test_lib",
    ],
)

pytype_strict_library(
    name = "channel_util_lib",
    srcs = ["channel_util.py"],
    deps = [
        ":env_lib",
        ":util_lib",
        third_party("grpc"),
    ],
)

pytype_strict_library(
    name = "olcs_session_stub",
    srcs = ["olcs_session_stub.py"],
    deps = [
        ":file_util_lib",
        ":olcs_session_client_lib",
        "//google/protobuf:duration_py_pb2",
        "//net/grpc/python:grpc",
        "@com_google_deviceinfra//src/devtools/mobileharness/infra/ats/server/proto:service_py_proto",
        "@com_google_deviceinfra//src/devtools/mobileharness/infra/client/longrunningservice/proto:session_py_proto",
        "@com_google_deviceinfra//src/devtools/mobileharness/infra/client/longrunningservice/proto:session_service_py_proto",
        "//multitest_transport/models:ndb_models_lib",
        "@tradefed_cluster//tradefed_cluster:api_messages_lib",
        "@tradefed_cluster//tradefed_cluster:common_lib",
    ],
)

pytype_strict_library(
    name = "olcs_session_client_lib",
    srcs = ["olcs_session_client.py"],
    deps = [
        ":channel_util_lib",
        "@com_google_deviceinfra//src/devtools/common/metrics/stability/util:grpc_error_util_lib",
        "@com_google_deviceinfra//src/devtools/mobileharness/infra/client/longrunningservice/proto:session_service_py_grpc",
        "@com_google_deviceinfra//src/devtools/mobileharness/infra/client/longrunningservice/proto:session_service_py_proto",
        third_party("grpc"),
    ],
)

py_test(
    name = "olcs_session_client_test",
    srcs = [
        "olcs_session_client_test.py",
    ],
    deps = [
        ":olcs_session_client_lib",
        "//net/grpc/python:grpc",
        "@com_google_deviceinfra//src/devtools/mobileharness/infra/client/longrunningservice/proto:session_py_proto",
        "@com_google_deviceinfra//src/devtools/mobileharness/infra/client/longrunningservice/proto:session_service_py_grpc",
        "@com_google_deviceinfra//src/devtools/mobileharness/infra/client/longrunningservice/proto:session_service_py_proto",
        third_party("absl/testing:absltest"),
        "//third_party/py/grpc_testing",
    ],
)

pytype_strict_library(
    name = "olcs_lab_info_client_lib",
    srcs = ["olcs_lab_info_client.py"],
    deps = [
        ":channel_util_lib",
        "@com_google_deviceinfra//src/devtools/common/metrics/stability/util:grpc_error_util_lib",
        "@com_google_deviceinfra//src/devtools/mobileharness/shared/labinfo/proto:lab_info_service_py_grpc",
        "@com_google_deviceinfra//src/devtools/mobileharness/shared/labinfo/proto:lab_info_service_py_proto",
        third_party("grpc"),
    ],
)

py_test(
    name = "olcs_lab_info_client_test",
    srcs = [
        "olcs_lab_info_client_test.py",
    ],
    deps = [
        ":olcs_lab_info_client_lib",
        "@com_google_deviceinfra//src/devtools/mobileharness/shared/labinfo/proto:lab_info_service_py_grpc",
        "@com_google_deviceinfra//src/devtools/mobileharness/shared/labinfo/proto:lab_info_service_py_proto",
        third_party("absl/testing:absltest"),
    ],
)

pytype_strict_library(
    name = "olcs_lab_record_client_lib",
    srcs = ["olcs_lab_record_client.py"],
    deps = [
        ":channel_util_lib",
        "@com_google_deviceinfra//src/devtools/common/metrics/stability/util:grpc_error_util_lib",
        "@com_google_deviceinfra//src/devtools/mobileharness/infra/master/rpc/proto:lab_record_service_py_grpc",
        "@com_google_deviceinfra//src/devtools/mobileharness/infra/master/rpc/proto:lab_record_service_py_proto",
        third_party("grpc"),
    ],
)

pytype_strict_library(
    name = "lru_cache",
    srcs = ["lru_cache.py"],
)

pytype_strict_library(
    name = "olcs_lab_info_stub",
    srcs = ["olcs_lab_info_stub.py"],
    deps = [
        ":olcs_lab_info_client_lib",
        "@com_google_deviceinfra//src/devtools/mobileharness/api/model/proto:device_py_pb2",
        "@com_google_deviceinfra//src/devtools/mobileharness/shared/labinfo/proto:lab_info_service_py_proto",
        "//third_party/py/endpoints:endpoints_library",
        "//third_party/py/protorpc:protorpc_all",
        "@tradefed_cluster//tradefed_cluster:api_messages_lib",
        "@tradefed_cluster//tradefed_cluster:common_lib",
    ],
)

py_test(
    name = "olcs_lab_info_stub_test",
    srcs = ["olcs_lab_info_stub_test.py"],
    deps = [
        ":olcs_lab_info_client_lib",
        ":olcs_lab_info_stub",
        "@com_google_deviceinfra//src/devtools/mobileharness/api/model/proto:device_py_pb2",
        "@com_google_deviceinfra//src/devtools/mobileharness/shared/labinfo/proto:lab_info_service_py_proto",
        "//third_party/py/absl/testing:absltest",
        "@tradefed_cluster//tradefed_cluster:api_messages_lib",
    ],
)

py_test(
    name = "lru_cache_test",
    srcs = ["lru_cache_test.py"],
    deps = [
        ":lru_cache",
        third_party("absl/testing:absltest"),
    ],
)

py_test(
    name = "olcs_lab_record_client_test",
    srcs = [
        "olcs_lab_record_client_test.py",
    ],
    deps = [
        ":olcs_lab_record_client_lib",
        "@com_google_deviceinfra//src/devtools/mobileharness/infra/master/rpc/proto:lab_record_service_py_grpc",
        "@com_google_deviceinfra//src/devtools/mobileharness/infra/master/rpc/proto:lab_record_service_py_proto",
        third_party("absl/testing:absltest"),
    ],
)

pytype_strict_library(
    name = "worker_lab_health_client",
    srcs = ["worker_lab_health_client.py"],
    deps = [
        ":channel_util_lib",
        "//net/grpc/python:grpc",
        "@com_google_deviceinfra//src/devtools/common/metrics/stability/util:grpc_error_util_lib",
        "@com_google_deviceinfra//src/devtools/deviceinfra/host/daemon/proto:health_service_py_grpc",
        "@com_google_deviceinfra//src/devtools/deviceinfra/host/daemon/proto:health_service_py_proto",
    ],
)

py_test(
    name = "worker_lab_health_client_test",
    srcs = ["worker_lab_health_client_test.py"],
    deps = [
        ":channel_util_lib",
        ":worker_lab_health_client",
        "//net/grpc/python:grpc",
        "@com_google_deviceinfra//src/devtools/deviceinfra/host/daemon/proto:health_service_py_proto",
        "//third_party/py/absl/testing:absltest",
        "//third_party/py/grpc_testing",
    ],
)

py_test(
    name = "xts_result_test",
    srcs = [
        "xts_result_test.py",
    ],
    data = [
        "test_data/test_result.xml",
        "test_data/test_result_missing_runtime.xml",
    ],
    deps = [
        ":xts_result_lib",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
        third_party("absl/testing:absltest"),
    ],
)
