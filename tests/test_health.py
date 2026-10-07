import asyncio
import unittest

from main import make_health_response


class HealthResponseTests(unittest.TestCase):
    def test_ready_health_route_returns_success(self):
        response = make_health_response("GET", "/health", True)
        self.assertTrue(response.startswith(b"HTTP/1.1 200 OK\r\n"))
        self.assertIn(b'{"status":"ok"}', response)

    def test_health_route_reports_starting_until_bot_is_ready(self):
        response = make_health_response("GET", "/", False)
        self.assertTrue(response.startswith(b"HTTP/1.1 503 Service Unavailable\r\n"))
        self.assertIn(b'{"status":"starting"}', response)

    def test_unknown_paths_and_methods_are_rejected(self):
        not_found = make_health_response("GET", "/other", True)
        method_not_allowed = make_health_response("POST", "/health", True)
        self.assertTrue(not_found.startswith(b"HTTP/1.1 404 Not Found\r\n"))
        self.assertTrue(method_not_allowed.startswith(b"HTTP/1.1 405 Method Not Allowed\r\n"))


class HealthServerTests(unittest.IsolatedAsyncioTestCase):
    async def test_http_health_handler_serves_ready_status_over_socket(self):
        class ReadyState:
            @staticmethod
            def is_ready():
                return True

        async def handle(reader, writer):
            await BotPrincipal._handle_health_request(ReadyState(), reader, writer)

        from main import BotPrincipal

        server = await asyncio.start_server(handle, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        writer = None
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            writer.write(b"GET /health HTTP/1.1\r\nHost: localhost\r\n\r\n")
            await writer.drain()
            response = await reader.read()
            self.assertIn(b"HTTP/1.1 200 OK", response)
            self.assertIn(b'{"status":"ok"}', response)
        finally:
            if writer is not None:
                writer.close()
                await writer.wait_closed()
            server.close()
            await server.wait_closed()


if __name__ == "__main__":
    unittest.main()
