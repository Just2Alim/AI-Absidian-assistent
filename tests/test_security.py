import unittest

from backend.security import is_loopback_host, is_valid_token, token_fingerprint


class SecurityTests(unittest.TestCase):
    def test_loopback_detection(self):
        self.assertTrue(is_loopback_host("127.0.0.1"))
        self.assertTrue(is_loopback_host("::1"))
        self.assertFalse(is_loopback_host("192.168.0.10"))

    def test_token_validation(self):
        fingerprint = token_fingerprint()
        self.assertEqual(len(fingerprint), 12)
        self.assertFalse(is_valid_token("definitely-wrong"))


if __name__ == "__main__":
    unittest.main()
