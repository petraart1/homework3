import unittest
import subprocess
import yaml
import os


class TestConfigConverter(unittest.TestCase):
    def run_config_converter(self, input_text: str):

        script_path = os.path.join(os.path.dirname(__file__), 'main.py')
        process = subprocess.Popen(
            ["python3", script_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        out, err = process.communicate(input_text)
        if process.returncode != 0:
            self.fail(f"Process failed with code {process.returncode}.\nStderr:\n{err}")
        try:
            return yaml.safe_load(out)
        except yaml.YAMLError as e:
            self.fail(f"Failed to parse YAML output.\nOutput:\n{out}\nError:\n{e}")

    def test_simple_table(self):
        input_text = """table([
          key = "value"
        ])"""
        result = self.run_config_converter(input_text)
        self.assertEqual(result, {"key": "value"})

    def test_boolean_and_numbers(self):
        input_text = """
        count = 3;
        table([
          enabled = true,
          retries = ?{count},
          description = "Test run"
        ])
        """
        result = self.run_config_converter(input_text)
        self.assertEqual(result, {
            "enabled": True,
            "retries": 3,
            "description": "Test run"
        })

    def test_nested_tables(self):
        input_text = """
        table([
          database = table([
            host = "localhost",
            port = 5432
          ]),
          service = table([
            url = "http://example.com",
            timeout = 10
          ])
        ])
        """
        result = self.run_config_converter(input_text)
        self.assertEqual(result, {
            "database": {
                "host": "localhost",
                "port": 5432
            },
            "service": {
                "url": "http://example.com",
                "timeout": 10
            }
        })

    def test_empty_table(self):
        input_text = """table([])"""
        result = self.run_config_converter(input_text)
        self.assertEqual(result, {})



if __name__ == '__main__':
    unittest.main()