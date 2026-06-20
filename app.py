"""
Academic Manuscript Format Checker
A Streamlit web application for checking and fixing manuscript formatting

Main Application Entry Point
"""

import streamlit as st
import os
import subprocess
import traceback
from io import BytesIO
from datetime import datetime

# Import modules
from modules.template_extractor import TemplateExtractor
from modules.paragraph_classifier import ParagraphClassifier, ParagraphType
from modules.manuscript_checker import ManuscriptChecker
from modules.auto_fixer import (
    AutoFixer,
    summarize_remaining_issues,
    validate_fixed_document,
    validate_post_fix_result,
)
from modules.report_generator import ReportGenerator
from modules.llm_integration import create_llm_integration, fallback_explain_issue
from modules.utils import pdf_to_docx, docx_to_pdf, PDF2DOCX_AVAILABLE, DOCX2PDF_AVAILABLE
from config import APP_TITLE, APP_VERSION, DEFAULT_RULES, COLORS

# Page configuration
st.set_page_config(
    page_title=APP_TITLE,
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded"
)


def get_build_commit() -> str:
    """Return the current Git commit short hash when available."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
            check=True,
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


def get_server_nvidia_api_key() -> str:
    """Return a server-managed NVIDIA API key without exposing it in the UI."""
    key_names = [
        "NVIDIA_API_KEY",
        "NVIDIA_NIM_API_KEY",
        "NVIDIA_API_TOKEN",
        "nvidia_api_key",
        "nvidia_nim_api_key",
        "nvidia_api_token",
    ]
    secret_candidates = []
    try:
        secret_candidates.extend(st.secrets.get(name, "") for name in key_names)
        llm_secrets = st.secrets.get("llm", {})
        secret_candidates.extend(llm_secrets.get(name, "") for name in key_names)
    except Exception:
        pass

    secret_candidates.extend(os.environ.get(name, "") for name in key_names)
    return next((key for key in secret_candidates if key), "")


def ensure_llm_connection() -> bool:
    """Connect to the server-managed LLM once when AI explanations are enabled."""
    if st.session_state.llm and st.session_state.llm.is_available():
        return True
    if st.session_state.get("llm_connection_attempted"):
        return False

    st.session_state.llm_connection_attempted = True
    api_key = get_server_nvidia_api_key()
    if not api_key:
        st.session_state.llm = None
        return False

    st.session_state.llm = create_llm_integration(api_key=api_key)
    if st.session_state.llm.is_available():
        st.session_state.llm_source = "server"
        return True

    st.session_state.llm = None
    return False

# Load custom CSS
def load_css():
    css_path = os.path.join(os.path.dirname(__file__), "assets", "styles.css")
    if os.path.exists(css_path):
        with open(css_path) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    else:
        # Inline CSS if file not found
        st.markdown("""
        <style>
            .main-header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 20px;
                border-radius: 10px;
                color: white;
                margin-bottom: 20px;
            }
            .score-card {
                padding: 20px;
                border-radius: 10px;
                text-align: center;
                margin: 10px 0;
            }
            .score-good { background: #d4edda; border: 2px solid #28a745; }
            .score-medium { background: #fff3cd; border: 2px solid #ffc107; }
            .score-poor { background: #f8d7da; border: 2px solid #dc3545; }
            .issue-card {
                padding: 15px;
                border-radius: 8px;
                margin: 10px 0;
                border-left: 4px solid;
            }
            .issue-error { background: #fff5f5; border-color: #dc3545; }
            .issue-warning { background: #fffbf0; border-color: #ffc107; }
            .rules-display {
                background: #f8f9fa;
                padding: 15px;
                border-radius: 8px;
                margin: 10px 0;
            }
            .stTabs [data-baseweb="tab-list"] {
                gap: 10px;
            }
            .stTabs [data-baseweb="tab"] {
                padding: 10px 20px;
                border-radius: 5px;
            }
        </style>
        """, unsafe_allow_html=True)

load_css()


def init_session_state():
    """Initialize session state variables"""
    if "template_rules" not in st.session_state:
        st.session_state.template_rules = None
    if "template_uploaded" not in st.session_state:
        st.session_state.template_uploaded = False
    if "manuscript_uploaded" not in st.session_state:
        st.session_state.manuscript_uploaded = False
    if "check_result" not in st.session_state:
        st.session_state.check_result = None
    if "classifications" not in st.session_state:
        st.session_state.classifications = []
    if "changes" not in st.session_state:
        st.session_state.changes = []
    if "fixed_doc_bytes" not in st.session_state:
        st.session_state.fixed_doc_bytes = None
    if "report_bytes" not in st.session_state:
        st.session_state.report_bytes = None
    if "post_fix_result" not in st.session_state:
        st.session_state.post_fix_result = None
    if "post_fix_validation" not in st.session_state:
        st.session_state.post_fix_validation = None
    if "llm" not in st.session_state:
        st.session_state.llm = None
    if "llm_connection_attempted" not in st.session_state:
        st.session_state.llm_connection_attempted = False
    if "llm_source" not in st.session_state:
        st.session_state.llm_source = ""
    if "ai_explanations_enabled" not in st.session_state:
        st.session_state.ai_explanations_enabled = False
    if "manuscript_bytes" not in st.session_state:
        st.session_state.manuscript_bytes = None
    if "manuscript_filename" not in st.session_state:
        st.session_state.manuscript_filename = "manuscript.docx"
    if "highlighted_doc_bytes" not in st.session_state:
        st.session_state.highlighted_doc_bytes = None
    if "output_timestamp" not in st.session_state:
        st.session_state.output_timestamp = ""


def display_header():
    """Display application header"""
    st.markdown("""
    <div class="main-header">
        <h1 style="margin: 0;">Automated Manuscript Template Compliance Checker</h1>
        <p style="margin: 10px 0 0 0; opacity: 0.9;">
            Automatically check and fix manuscript formatting against journal templates
        </p>
    </div>
    """, unsafe_allow_html=True)


def display_exception(summary: str, error: Exception):
    """Display a user-safe error with optional technical details."""
    st.error(f"{summary}: {str(error)}")
    with st.expander("Technical details", expanded=False):
        st.code(traceback.format_exc())


def display_sidebar():
    """Display sidebar with template rules and settings"""
    with st.sidebar:
        st.header("Template Rules")

        # LLM Configuration
        with st.expander("AI Explanation Settings", expanded=False):
            st.caption(
                "AI is optional and is used only for issue explanations. "
                "Template extraction, compliance checking, auto-fix, and accuracy evaluation remain rule-based."
            )
            ai_enabled = st.checkbox(
                "Enable AI explanations",
                value=st.session_state.ai_explanations_enabled,
                help="Turn this on only when you want AI-generated explanations for detected issues."
            )
            st.session_state.ai_explanations_enabled = ai_enabled

            if not ai_enabled:
                st.session_state.llm = None
                st.session_state.llm_connection_attempted = False
                st.session_state.llm_source = ""
                st.info("AI explanations are disabled. Core checking is rule-based.")

            # Show current status
            if ai_enabled and ensure_llm_connection():
                st.success("AI explanations are using the server NVIDIA API key.")
                st.info("AI explanations are enabled. Core checking remains rule-based.")
                if st.button("Disconnect LLM"):
                    st.session_state.llm = None
                    st.session_state.llm_connection_attempted = False
                    st.session_state.llm_source = ""
                    st.session_state.ai_explanations_enabled = False
                    st.rerun()
            elif ai_enabled:
                st.warning(
                    "AI explanation service is not configured on this deployment. "
                    "Rule-based explanations will still be shown."
                )
                if os.environ.get("SHOW_LLM_KEY_OVERRIDE") == "1":
                    with st.expander("Developer key override", expanded=False):
                        st.caption("Optional for local testing only. Normal users do not need to enter an API key.")
                        api_key = st.text_input(
                            "NVIDIA API Key",
                            type="password",
                            placeholder="nvapi-xxxxxxxxxxxx",
                            help="Use only when the server-managed key is not configured."
                        )
                        if st.button("Connect with override key", type="primary"):
                            if api_key:
                                st.session_state.llm = create_llm_integration(api_key=api_key)
                                st.session_state.llm_connection_attempted = True
                                if st.session_state.llm.is_available():
                                    st.session_state.llm_source = "override"
                                    st.success("Connected successfully.")
                                    st.rerun()
                                else:
                                    st.session_state.llm = None
                                    st.error("Connection failed. Check the override key.")
                            else:
                                st.error("Please enter an API key")

        st.divider()

        # Display extracted rules if available
        if st.session_state.template_rules:
            rules = st.session_state.template_rules
            extraction_summary = rules.get("_extraction_summary", {})
            profile = rules.get("_profile", {})
            if extraction_summary:
                st.info(
                    f"Profile: {profile.get('name', 'Generic')} | "
                    f"{extraction_summary.get('extracted', 0)} extracted, "
                    f"{extraction_summary.get('inferred', 0)} inferred, "
                    f"{extraction_summary.get('default', 0)} defaulted"
                )

            # Show AI enhancement status
            if rules.get("_ai_enhanced"):
                st.success("AI-enhanced extraction")

            st.subheader("Extracted Text Styles")

            # Title style
            st.markdown("**Title Style:**")
            title = rules.get("title", {})
            bold_display = "Yes" if title.get('bold') else ("No" if title.get('bold') is False else "Auto")
            st.caption(f"Font: {title.get('font_name', 'Times New Roman')} | Size: {title.get('font_size', 24)}pt | Bold: {bold_display}")

            # Body style
            st.markdown("**Body Text Style:**")
            body = rules.get("body", {})
            st.caption(f"Font: {body.get('font_name', 'Times New Roman')} | Size: {body.get('font_size', 12)}pt")

            # Heading style
            st.markdown("**Heading Style:**")
            heading = rules.get("heading", {})
            bold_display = "Yes" if heading.get('bold') else ("No" if heading.get('bold') is False else "Auto")
            st.caption(f"Font: {heading.get('font_name', 'Times New Roman')} | Size: {heading.get('font_size', 14)}pt | Bold: {bold_display}")

            # Show margins in collapsed expander (optional viewing)
            with st.expander("Page Margins (Advanced)", expanded=False):
                margins = rules.get("margins", {})
                st.caption(f"L: {margins.get('left', 1.0):.2f}in | R: {margins.get('right', 1.0):.2f}in | T: {margins.get('top', 1.0):.2f}in | B: {margins.get('bottom', 1.0):.2f}in")
        else:
            st.info("Upload a template file to extract formatting rules")

        st.divider()

        # About section
        with st.expander("About"):
            st.markdown(f"""
            **{APP_TITLE}**
            Version: {APP_VERSION}
            Build: {get_build_commit()}

            This tool helps you:
            - Extract formatting rules from journal templates
            - Check manuscripts against templates
            - Auto-fix formatting issues
            - Generate comparison reports
            """)


def handle_template_upload(uploaded_file):
    """Handle template file upload and rule extraction"""
    if uploaded_file:
        try:
            file_bytes = uploaded_file.read()
            original_filename = uploaded_file.name
            file_name = original_filename.lower()

            # Convert PDF to DOCX if needed
            if file_name.endswith('.pdf'):
                with st.spinner("Converting PDF to DOCX..."):
                    try:
                        file_bytes = pdf_to_docx(file_bytes)
                        st.info("PDF converted to DOCX for processing")
                    except Exception as e:
                        st.error(f"Failed to convert PDF: {str(e)}")
                        return

            with st.spinner("Extracting formatting rules from template..."):
                extractor = TemplateExtractor(llm_integration=None)
                extractor.load(BytesIO(file_bytes), template_name=original_filename)
                rules = extractor.extract_all_rules()

                st.session_state.template_rules = rules
                st.session_state.template_uploaded = True

                summary = rules.get("_extraction_summary", {})
                st.success(
                    "Template rules processed: "
                    f"{summary.get('extracted', 0)} extracted, "
                    f"{summary.get('inferred', 0)} inferred, "
                    f"{summary.get('default', 0)} defaulted."
                )

                # Display summary - user-friendly view
                with st.expander("View Extracted Rules Summary", expanded=True):
                    st.text(extractor.get_rules_summary())

        except Exception as e:
            display_exception("Error extracting template rules", e)


def handle_manuscript_check(uploaded_file):
    """Handle manuscript upload and format checking"""
    if uploaded_file:
        try:
            # Store manuscript bytes and filename for later use
            manuscript_bytes = uploaded_file.read()
            original_filename = uploaded_file.name
            file_name = original_filename.lower()

            # Store original filename (without extension) for download
            base_name = original_filename.rsplit('.', 1)[0] if '.' in original_filename else original_filename
            st.session_state.manuscript_filename = base_name

            # Convert PDF to DOCX if needed
            if file_name.endswith('.pdf'):
                with st.spinner("Converting PDF to DOCX..."):
                    try:
                        manuscript_bytes = pdf_to_docx(manuscript_bytes)
                        st.info("PDF converted to DOCX for processing")
                    except Exception as e:
                        st.error(f"Failed to convert PDF: {str(e)}")
                        return None

            st.session_state.manuscript_bytes = manuscript_bytes

            with st.spinner("Analyzing manuscript formatting..."):
                # Use template rules or defaults
                rules = st.session_state.template_rules or DEFAULT_RULES

                # Warn user if using default rules
                if not st.session_state.template_rules:
                    st.warning("No template uploaded. Using default formatting rules (JIWE style). For accurate results, please upload a template file first.")

                # Core checking is rule-based. LLM is not used for compliance decisions.
                checker = ManuscriptChecker(rules, None)
                checker.load_manuscript(BytesIO(manuscript_bytes))

                # Run all checks
                result = checker.check_all()

                st.session_state.check_result = result
                st.session_state.classifications = result.classifications
                st.session_state.manuscript_uploaded = True
                st.session_state.changes = []
                st.session_state.fixed_doc_bytes = None
                st.session_state.highlighted_doc_bytes = None
                st.session_state.report_bytes = None
                st.session_state.post_fix_result = None
                st.session_state.post_fix_validation = None

                return result

        except Exception as e:
            display_exception("Error checking manuscript", e)

    return None


def display_check_results(result):
    """Display format check results"""
    st.header("Format Check Results")

    # Compliance score card
    score = result.compliance_score
    if score >= 80:
        score_class = "score-good"
        score_emoji = ""
    elif score >= 60:
        score_class = "score-medium"
        score_emoji = ""
    else:
        score_class = "score-poor"
        score_emoji = ""
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(f"""
        <div class="score-card {score_class}">
            <h2 style="margin: 0;">{score}%</h2>
            <p style="margin: 5px 0 0 0;">Compliance Index</p>
        </div>
        """, unsafe_allow_html=True)
        st.caption("UI index only. FYP accuracy is evaluated with Precision, Recall, and F1.")

    with col2:
        st.markdown(f"""
        <div class="score-card" style="background: #e3f2fd; border: 2px solid #2196f3;">
            <h2 style="margin: 0;">{result.total_issues}</h2>
            <p style="margin: 5px 0 0 0;">Issues Found</p>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        stats = result.statistics
        st.markdown(f"""
        <div class="score-card" style="background: #f3e5f5; border: 2px solid #9c27b0;">
            <h2 style="margin: 0;">{stats.get('total_words', 0)}</h2>
            <p style="margin: 5px 0 0 0;">Total Words</p>
        </div>
        """, unsafe_allow_html=True)

    # Document structure
    st.subheader("Document Structure")
    structure = result.document_structure
    structure_details = structure if isinstance(structure.get("sections"), dict) else None
    if structure_details:
        structure = {
            name: details.get("found", False)
            for name, details in structure_details.get("sections", {}).items()
        }

    sections = (
        structure_details.get("expected_order", [])
        if structure_details else ["abstract", "keywords", "introduction", "conclusion", "references"]
    )
    structure_cols = st.columns(max(1, len(sections)))

    for i, section in enumerate(sections):
        with structure_cols[i]:
            found = structure.get(section, False)
            status = "Yes" if found else "No"
            st.markdown(f"**{section.title()}**")
            st.write(status)

    if structure_details:
        format_rows = []
        for section in sections:
            details = structure_details.get("sections", {}).get(section, {})
            format_rows.append({
                "Section": section.title(),
                "Found": "Yes" if details.get("found") else "No",
                "Paragraph": details.get("index"),
                "Format Evidence": details.get("format_status", "not_checked"),
            })
        st.dataframe(format_rows, use_container_width=True, hide_index=True)
        if structure_details.get("order_correct", True):
            st.caption("Section order check: passed")
        else:
            st.warning("Section order check: required sections may be out of order.")

    # Issues by category
    st.subheader("Issues by Category")

    tabs = st.tabs([
        "All Issues", "Margins", "Journal Header", "Title", "Body Text",
        "Headings", "Structure", "References"
    ])

    with tabs[0]:
        # All issues view
        if result.total_issues == 0:
            st.success("No formatting issues found.")
        else:
            for category, issues in result.issues_by_category.items():
                if issues:
                    with st.expander(f"**{category.replace('_', ' ').title()}** ({len(issues)} issues)", expanded=False):
                        for issue in issues:
                            severity_class = "issue-error" if issue.severity == "error" else "issue-warning"
                            st.markdown(f"""
                            <div class="issue-card {severity_class}">
                                <strong>{issue.location}</strong><br>
                                {issue.description}<br>
                                <span style="color: #dc3545;">Current: {issue.current_value}</span> |
                                <span style="color: #28a745;">Expected: {issue.expected_value}</span>
                            </div>
                            """, unsafe_allow_html=True)

    # Category-specific tabs
    category_map = {
        1: "margins",
        2: "journal_header",
        3: "title",
        4: "body_text",
        5: "headings",
        6: "structure",
        7: "references"
    }

    for tab_idx, category in category_map.items():
        with tabs[tab_idx]:
            issues = result.issues_by_category.get(category, [])
            if not issues:
                st.success(f"No {category.replace('_', ' ')} issues found")
            else:
                for issue_idx, issue in enumerate(issues):
                    severity_label = "Error" if issue.severity == "error" else "Warning"
                    st.markdown(f"""
                    **{severity_label}: {issue.location}**
                    - {issue.description}
                    - Current: `{issue.current_value}` Expected: `{issue.expected_value}`
                    """)

                    # Optional AI explanation, with deterministic fallback when unavailable.
                    if st.session_state.ai_explanations_enabled:
                        if st.button(f"Explain", key=f"explain_{category}_{tab_idx}_{issue_idx}_{issue.paragraph_index}"):
                            issue_payload = {
                                "category": category,
                                "location": issue.location,
                                "description": issue.description,
                                "current_value": issue.current_value,
                                "expected_value": issue.expected_value,
                                "severity": issue.severity,
                            }
                            if ensure_llm_connection():
                                explanation = st.session_state.llm.explain_error(issue_payload)
                            else:
                                explanation = fallback_explain_issue(issue_payload)
                            st.info(explanation)


def handle_auto_fix():
    """Handle auto-fix process"""
    if not st.session_state.manuscript_bytes:
        st.warning("Please upload a manuscript first")
        return

    try:
        with st.spinner("Applying formatting fixes..."):
            rules = st.session_state.template_rules or DEFAULT_RULES
            classifications = st.session_state.classifications

            # Create auto-fixer
            issues_by_category = {}
            if st.session_state.check_result:
                issues_by_category = st.session_state.check_result.issues_by_category
            fixer = AutoFixer(rules, classifications, issues_by_category=issues_by_category)
            fixer.load_manuscript(BytesIO(st.session_state.manuscript_bytes))

            # Apply fixes
            fixed_doc, changes = fixer.fix_all()

            st.session_state.changes = changes
            st.session_state.fixed_doc_bytes = fixer.get_fixed_document_bytes()
            st.session_state.highlighted_doc_bytes = fixer.get_highlighted_document_bytes()
            st.session_state.output_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            st.session_state.post_fix_result = validate_fixed_document(
                rules,
                st.session_state.fixed_doc_bytes,
            )
            st.session_state.post_fix_validation = validate_post_fix_result(
                st.session_state.check_result,
                st.session_state.post_fix_result,
            )

            # Generate report
            report_gen = ReportGenerator(
                rules, changes, st.session_state.check_result
            )
            report_gen.generate_comparison_report()
            st.session_state.report_bytes = report_gen.get_report_bytes()

            validation = st.session_state.post_fix_validation
            if validation and validation.is_safe:
                st.success(f"{len(changes)} formatting fixes applied. {validation.message}")
            elif validation:
                st.warning(f"{len(changes)} formatting fixes applied. {validation.message}")
            else:
                st.success(f"{len(changes)} formatting fixes applied.")

            return changes

    except Exception as e:
        display_exception("Error during auto-fix", e)

    return None


def display_comparison_view(changes):
    """Display structured change records without parsing free-text strings."""
    st.header("Format Changes Applied")

    if not changes:
        st.info("No changes were made to the document")
        return

    changes_by_type = {}
    for change in changes:
        changes_by_type[change.change_type] = changes_by_type.get(change.change_type, 0) + 1
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Properties Changed", len(changes))
    with col2:
        most_common = max(changes_by_type, key=changes_by_type.get)
        st.metric("Most Common", most_common.replace("_", " ").title())
    with col3:
        st.metric("Change Types", len(changes_by_type))

    with st.expander("Changes Summary by Type", expanded=False):
        for change_type, count in sorted(changes_by_type.items(), key=lambda item: -item[1]):
            st.write(f"- **{change_type.replace('_', ' ').title()}**: {count} properties")

    table_data = []
    for index, change in enumerate(changes, 1):
        text_preview = change.text_preview[:60] + "..." if len(change.text_preview) > 60 else change.text_preview
        table_data.append({
            "#": index,
            "Paragraph": change.paragraph_index + 1 if change.paragraph_index >= 0 else "Document",
            "Type": change.change_type,
            "Property": change.property_name,
            "Current Value": change.current_value or change.before,
            "Target Value": change.target_value or change.after,
            "Text": text_preview,
            "Evidence": change.evidence,
        })

    import pandas as pd
    df = pd.DataFrame(table_data)
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.success(f"Recorded {len(changes)} formatting property changes")


def display_post_fix_validation():
    """Display checker results after auto-fix."""
    validation = st.session_state.get("post_fix_validation")
    if not validation:
        return

    st.subheader("Post-Fix Validation")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Issues Before", validation.before_issues)
    with col2:
        st.metric("Issues After", validation.after_issues, delta=validation.issue_delta)
    with col3:
        st.metric("Compliance After", f"{validation.after_score}%", delta=validation.score_delta)

    if validation.is_safe:
        st.success(validation.message)
    else:
        st.warning(validation.message)
        if validation.new_or_increased_categories:
            category_text = ", ".join(
                f"{category.replace('_', ' ').title()}: +{count}"
                for category, count in sorted(validation.new_or_increased_categories.items())
            )
            st.caption(f"Increased categories: {category_text}")

    remaining_result = st.session_state.get("post_fix_result")
    remaining_rows = summarize_remaining_issues(remaining_result) if remaining_result else []
    if remaining_rows:
        with st.expander("Remaining Issues After Auto-Fix", expanded=not validation.is_safe):
            st.dataframe(remaining_rows, use_container_width=True, hide_index=True)
            st.caption("These issues still need manual review or a more specific journal rule.")
    else:
        st.success("No remaining issues were detected after auto-fix.")


def display_download_section():
    """Display download buttons for output files"""
    st.header("Download Results")

    # Format selection
    download_format = st.radio(
        "Select download format:",
        ["DOCX (Word)", "PDF"],
        horizontal=True,
        help="PDF download requires Microsoft Word installed on the server"
    )
    st.caption(
        "Corrected document contains applied fixes. Highlighted document keeps the original manuscript "
        "and marks changed locations in yellow. Detailed report explains what changed."
    )

    output_timestamp = st.session_state.output_timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.session_state.fixed_doc_bytes:
            # Get original filename and add 'corrected_' prefix
            base_filename = st.session_state.manuscript_filename
            if download_format == "DOCX (Word)":
                st.download_button(
                    label="Download Corrected Document (DOCX)",
                    data=st.session_state.fixed_doc_bytes,
                    file_name=f"corrected_{base_filename}_{output_timestamp}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True
                )
            else:
                # PDF download
                if DOCX2PDF_AVAILABLE:
                    if st.button("Convert and Download as PDF", use_container_width=True, key="download_corrected_pdf"):
                        with st.spinner("Converting to PDF... (requires MS Word)"):
                            try:
                                pdf_bytes = docx_to_pdf(st.session_state.fixed_doc_bytes)
                                st.download_button(
                                    label="Download PDF",
                                    data=pdf_bytes,
                                    file_name=f"corrected_{base_filename}_{output_timestamp}.pdf",
                                    mime="application/pdf",
                                    use_container_width=True,
                                    key="download_pdf_corrected"
                                )
                            except Exception as e:
                                st.error(f"PDF conversion failed: {str(e)}")
                                st.info("Make sure Microsoft Word is installed on the system")
                else:
                    st.warning("PDF conversion not available (install docx2pdf)")
        else:
            st.button("Download Corrected Document", disabled=True, use_container_width=True)

    with col2:
        if st.session_state.highlighted_doc_bytes:
            base_filename = st.session_state.manuscript_filename
            st.download_button(
                label="Download Original with Highlighted Changes (DOCX)",
                data=st.session_state.highlighted_doc_bytes,
                file_name=f"highlighted_{base_filename}_{output_timestamp}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
                help="Highlights are shown on the original manuscript to indicate locations changed in the corrected document."
            )
        else:
            st.button("Download Original with Highlighted Changes", disabled=True, use_container_width=True)

    with col3:
        if st.session_state.report_bytes:
            base_filename = st.session_state.manuscript_filename
            if download_format == "DOCX (Word)":
                st.download_button(
                    label="Download Detailed Report (DOCX)",
                    data=st.session_state.report_bytes,
                    file_name=f"{base_filename}_report_{output_timestamp}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True
                )
            else:
                # PDF download
                if DOCX2PDF_AVAILABLE:
                    if st.button("Convert and Download Report as PDF", use_container_width=True, key="download_report_pdf"):
                        with st.spinner("Converting to PDF... (requires MS Word)"):
                            try:
                                pdf_bytes = docx_to_pdf(st.session_state.report_bytes)
                                st.download_button(
                                    label="Download PDF Report",
                                    data=pdf_bytes,
                                    file_name=f"{base_filename}_report_{output_timestamp}.pdf",
                                    mime="application/pdf",
                                    use_container_width=True,
                                    key="download_pdf_report"
                                )
                            except Exception as e:
                                st.error(f"PDF conversion failed: {str(e)}")
                                st.info("Make sure Microsoft Word is installed on the system")
                else:
                    st.warning("PDF conversion not available (install docx2pdf)")
        else:
            st.button("Download Detailed Report", disabled=True, use_container_width=True)


def main():
    """Main application function"""
    init_session_state()
    display_header()
    display_sidebar()

    # Main content area
    st.header("Upload Documents")

    # Show PDF support status
    col_info1, col_info2 = st.columns(2)
    with col_info1:
        if PDF2DOCX_AVAILABLE:
            st.success("PDF Upload Supported")
        else:
            st.warning("PDF Upload not available (install pdf2docx)")
    with col_info2:
        if DOCX2PDF_AVAILABLE:
            st.success("PDF Download Supported")
        else:
            st.warning("PDF Download not available (install docx2pdf)")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("1. Upload Template")
        st.write("Upload a journal template (.docx or .pdf) to extract formatting rules")

        template_file = st.file_uploader(
            "Choose template file",
            type=["docx", "pdf"] if PDF2DOCX_AVAILABLE else ["docx"],
            key="template_uploader",
            help="Upload the journal's template document (DOCX or PDF)"
        )

        if template_file:
            handle_template_upload(template_file)

        # Option to use default rules
        if not st.session_state.template_uploaded:
            if st.button("Use Default Rules"):
                st.session_state.template_rules = DEFAULT_RULES
                st.session_state.template_uploaded = True
                st.success("Using default IEEE-style formatting rules")
                st.rerun()

    with col2:
        st.subheader("2. Upload Manuscript")
        st.write("Upload your manuscript (.docx or .pdf) to check formatting")

        manuscript_file = st.file_uploader(
            "Choose manuscript file",
            type=["docx", "pdf"] if PDF2DOCX_AVAILABLE else ["docx"],
            key="manuscript_uploader",
            help="Upload your manuscript document to check (DOCX or PDF)"
        )

        if manuscript_file and st.button("Check Format", type="primary"):
            result = handle_manuscript_check(manuscript_file)
            if result:
                st.rerun()

    # Display results if check has been performed
    if st.session_state.check_result:
        st.divider()
        display_check_results(st.session_state.check_result)

        # Auto-fix section
        st.divider()
        st.header("Auto-Fix Formatting")

        col1, col2 = st.columns([3, 1])

        with col1:
            st.write("""
            Click the button below to automatically fix all formatting issues.
            The system will:
            - Fix page margins
            - Correct title formatting
            - Adjust body text font and size
            - Fix heading styles
            - Preserve special formatting (italic, underline, subscript, etc.)
            """)

        with col2:
            if st.button("Auto-Fix All", type="primary", use_container_width=True):
                changes = handle_auto_fix()
                if changes:
                    st.rerun()

        # Display comparison view if fixes have been applied
        if st.session_state.changes:
            st.divider()
            display_comparison_view(st.session_state.changes)
            display_post_fix_validation()

            # Download section
            st.divider()
            display_download_section()

    # Footer
    st.divider()
    st.markdown("""
    <div style="text-align: center; color: #666; padding: 20px;">
        <p>Automated Manuscript Template Compliance Checker | Built with Streamlit</p>
        <p>Final Year Project 2025</p>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
