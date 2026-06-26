import unittest

from app import get_download_format_options, get_pdf_download_notice


class DownloadOptionsTest(unittest.TestCase):
    def test_pdf_format_is_hidden_when_conversion_is_unavailable(self):
        self.assertEqual(get_download_format_options(False), ["DOCX (Word)"])

    def test_pdf_format_is_available_when_conversion_is_supported(self):
        self.assertEqual(get_download_format_options(True), ["DOCX (Word)", "PDF"])

    def test_pdf_unavailable_notice_tells_user_to_download_docx(self):
        notice = get_pdf_download_notice(
            False,
            "PDF download is unavailable on this server. Please download DOCX instead.",
        )

        self.assertIn("PDF download is unavailable", notice)
        self.assertIn("DOCX", notice)

    def test_pdf_supported_notice_is_empty(self):
        self.assertEqual(get_pdf_download_notice(True, "PDF download is supported."), "")


if __name__ == "__main__":
    unittest.main()
