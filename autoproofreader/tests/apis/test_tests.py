import json

from autoproofreader.tests.common import AutoproofreaderTestCase

TEST_URL = "/ext/autoproofreader/{}/tests"


class DiluvianModelTest(AutoproofreaderTestCase):
    def test_get(self):
        self.fake_authentication()

        response = self.client.get(
            TEST_URL.format(self.test_project_id),
            data={"greeting": "hello world", "time": 1200},
        )
        parsed_response = json.loads(response.content.decode("utf-8"))
        expected_result = {
            "data": {},
            "POST": {},
            "query_params": {"greeting": "hello world", "time": 1200},
        }
        self.assertEqual(expected_result, parsed_response)

        response = self.client.get(
            TEST_URL.format(self.test_project_id),
            data={"greeting": "hello world", "time": 1200},
            content_type="application/json",
        )
        parsed_response = json.loads(response.content.decode("utf-8"))
        expected_result = {
            "data": {},
            "POST": {},
            "query_params": {"greeting": "hello world", "time": 1200},
        }
        self.assertEqual(expected_result, parsed_response)

    def test_put(self):
        self.fake_authentication()

        response = self.client.put(
            TEST_URL.format(self.test_project_id),
            data={"greeting": "hello world", "time": 1200},
        )
        parsed_response = json.loads(response.content.decode("utf-8"))
        expected_result = {
            "data": {},
            "POST": {},
            "query_params": {"greeting": "hello world", "time": 1200},
        }
        self.assertEqual(expected_result, parsed_response)

        response = self.client.put(
            TEST_URL.format(self.test_project_id),
            data={"greeting": "hello world", "time": 1200},
            content_type="application/json",
        )
        parsed_response = json.loads(response.content.decode("utf-8"))
        expected_result = {
            "data": {},
            "POST": {},
            "query_params": {"greeting": "hello world", "time": 1200},
        }
        self.assertEqual(expected_result, parsed_response)

    def test_delete(self):
        self.fake_authentication()

        response = self.client.delete(
            TEST_URL.format(self.test_project_id),
            data={"greeting": "hello world", "time": 1200},
        )
        parsed_response = json.loads(response.content.decode("utf-8"))
        expected_result = {
            "data": {},
            "POST": {},
            "query_params": {"greeting": "hello world", "time": 1200},
        }
        self.assertEqual(expected_result, parsed_response)

        response = self.client.delete(
            TEST_URL.format(self.test_project_id),
            data={"greeting": "hello world", "time": 1200},
            content_type="application/json",
        )
        parsed_response = json.loads(response.content.decode("utf-8"))
        expected_result = {
            "data": {},
            "POST": {},
            "query_params": {"greeting": "hello world", "time": 1200},
        }
        self.assertEqual(expected_result, parsed_response)