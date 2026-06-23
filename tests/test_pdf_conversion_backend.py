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

    def test_linux_uses_libreoffice_when_available(self):
        backend = resolve_docx_to_pdf_backend(
            system_name="Linux",
            docx2pdf_available=True,
            executable_finder=lambda name: "/usr/bin/soffice" if name == "soffice" else None,
        )

        self.assertEqual(backend, "libreoffice")

    def test_windows_can_use_docx2pdf_when_available(self):
        backend = resolve_docx_to_pdf_backend(
            system_name="Windows",
            docx2pdf_available=True,
            executable_finder=lambda name: None,
        )

        self.assertEqual(backend, "docx2pdf")


if __name__ == "__main__":
    unittest.main()
