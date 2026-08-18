"""Tests for extended router/contract coverage (Django, gRPC, GraphQL, Gin, Spring)."""

from __future__ import annotations

from app.analyzers.api_analyzer import ApiAnalyzer
from app.analyzers.source_graph import FileEntry, SourceGraph


def _a() -> ApiAnalyzer:
    return ApiAnalyzer()


def test_django_urlconf():
    src = "\n".join([
        "urlpatterns = [",
        "    path('', views.index, name='index'),",
        "    path('users/<int:pk>/', views.user_detail, name='user-detail'),",
        "    path('home', HomeView.as_view()),",
        "    path('api/', include('api.urls')),",
        "]",
    ])
    routes = _a()._django_urlconf(src, "urls.py")
    assert ("any", "", "views.index") in routes
    assert ("any", "users/<int:pk>/", "views.user_detail") in routes
    assert ("any", "home", "HomeView.as_view") in routes
    assert ("any", "api/", "include") in routes


def test_grpc_routes():
    src = (
        'syntax = "proto3";\n'
        "service Greeter {\n"
        "  rpc SayHello (HelloRequest) returns (HelloReply);\n"
        "  rpc SayGoodbye (GoodbyeRequest) returns (GoodbyeReply);\n"
        "}\n"
    )
    routes = _a()._grpc_routes(src, "greeter.proto")
    assert ("rpc", "/Greeter.SayHello", "Greeter.SayHello") in routes
    assert ("rpc", "/Greeter.SayGoodbye", "Greeter.SayGoodbye") in routes


def test_graphql_routes():
    src = (
        "type Query {\n"
        "  user(id: ID!): User\n"
        "  users(limit: Int): [User]\n"
        "}\n"
        "type Mutation {\n"
        "  createUser(input: UserInput!): User\n"
        "}\n"
    )
    routes = _a()._graphql_routes(src, "schema.graphql")
    assert ("query", "Query.user", "user") in routes
    assert ("query", "Query.users", "users") in routes
    assert ("mutation", "Mutation.createUser", "createUser") in routes


def test_gin_routes():
    src = 'r.GET("/ping", ping)\nr.POST("/users", createUser)\nr.Any("/any", anyHandler)'
    routes = _a()._gin_routes(src, "main.go")
    assert ("get", "/ping", "") in routes
    assert ("post", "/users", "") in routes
    assert ("any", "/any", "") in routes


def test_spring_routes():
    src = (
        "@RestController\n"
        '@RequestMapping("/api")\n'
        "class UserController {\n"
        '  @GetMapping("/users")\n'
        "  public List<User> list() {}\n"
        '  @PostMapping("/users")\n'
        "  public User create() {}\n"
        "}\n"
    )
    routes = _a()._spring_routes(src, "UserController.java")
    assert ("get", "/api/users", "") in routes
    assert ("post", "/api/users", "") in routes


def test_mock_patch_is_not_a_route():
    src = "@mock.patch('/django.core.foo')\ndef test_x():\n    pass"
    assert _a()._python_routes(src, "tests.py", {}) == []


def test_analyze_dispatches_multiple_frameworks(tmp_path):
    (tmp_path / "urls.py").write_text("urlpatterns = [path('x/', views.x)]", encoding="utf-8")
    (tmp_path / "s.proto").write_text("service S {\n  rpc M (A) returns (B);\n}", encoding="utf-8")
    (tmp_path / "s.graphql").write_text("type Query {\n  a: Int\n}", encoding="utf-8")
    files = [
        FileEntry(path="urls.py", language="python"),
        FileEntry(path="s.proto", language=""),
        FileEntry(path="s.graphql", language=""),
    ]
    spec = _a().analyze(str(tmp_path), files, SourceGraph(), {})
    frameworks = {e.framework for e in spec.endpoints}
    assert "Django" in frameworks
    assert "gRPC" in frameworks
    assert "GraphQL" in frameworks
