import unittest

from modules.utils import resolve_docx_to_pdf_backend


class PdfConversionBackendTest(unittest.TestCase):
    def test_linux_without_libreoffice_is_not_supported_even_when_docx2pdf_imports(self):
        backend = resolve_docx_to_pdf_backend(
            system_name="Linux",
            docx2pdf_available=True,
            executable_finder=lambda name: None,
        )

        self.assertIsNone(backend)

    def test_linux_libreoffice_is_not_used_for_final_pdf_download(self):
        backend = resolve_docx_to_pdf_backend(
            system_name="Linux",
            docx2pdf_available=True,
            executable_finder=lambda name: "/usr/bin/soffice" if name == "soffice" else None,
        )

        self.assertIsNone(backend)

    def test_linux_libreoffice_can_be_requested_for_non_final_conversion(self):
        backend = resolve_docx_to_pdf_backend(
            system_name="Linux",
            docx2pdf_available=True,
            executable_finder=lambda name: "/usr/bin/soffice" if name == "soffice" else None,
            allow_libreoffice=True,
        )

        self.assertEqual(backend, "libreoffice")

    def test_windows_prefers_microsoft_word_even_when_libreoffice_exists(self):
        backend = resolve_docx_to_pdf_backend(
            system_name="Windows",
            docx2pdf_available=True,
            executable_finder=lambda name: "C:/Program Files/LibreOffice/program/soffice.exe",
        )

        self.assertEqual(backend, "docx2pdf")

    def test_windows_can_use_docx2pdf_when_available(self):
        backend = resolve_docx_to_pdf_backend(
            system_name="Windows",
            docx2pdf_available=True,
            executable_finder=lambda name: None,
        )

        self.assertEqual(backend, "docx2pdf")


if __name__ == "__main__":
    unittest.main()
