from django.test import TestCase, Client, RequestFactory
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.auth.models import User
from core.models import HotspotCluster, UserReport
from core.admin import UserReportAdmin
from django.contrib.admin.sites import AdminSite


class CommunityReportingTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.factory = RequestFactory()
        # Create a sample HotspotCluster in Kochi, Kerala
        self.cluster = HotspotCluster.objects.create(
            city="Kochi",
            cluster_id=0,
            center_lat=9.9816,
            center_lng=76.2999,
            avg_risk_score=0.82,
            risk_level="High",
            accident_count=15,
            area_name="MG Road, Kochi"
        )

    def test_user_report_creation(self):
        """Test UserReport model creation and default values."""
        report = UserReport.objects.create(
            name="Test User",
            email="test@example.com",
            latitude=9.9820,
            longitude=76.3000,
            issue_type="pothole",
            description="Deep pothole on left lane.",
            status="Pending",
            coverage_status="InCoverage"
        )
        self.assertEqual(report.status, "Pending")
        self.assertEqual(report.coverage_status, "InCoverage")
        self.assertIn("Pothole", str(report))

    def test_submit_report_in_coverage(self):
        """Test submitting report near hotspot -> InCoverage status."""
        url = reverse("submit_report")
        data = {
            "name": "Anand Mohan",
            "email": "anand@example.com",
            "latitude": "9.9850",
            "longitude": "76.3010",
            "issue_type": "pothole",
            "description": "Large pothole causing traffic slowdown near junction."
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        json_resp = response.json()
        self.assertTrue(json_resp.get("success"))

        report = UserReport.objects.get(id=json_resp["report_id"])
        self.assertEqual(report.name, "Anand Mohan")
        self.assertEqual(report.status, "Pending")
        self.assertEqual(report.coverage_status, "InCoverage")

    def test_submit_report_out_of_coverage(self):
        """Test submitting report outside coverage area (e.g. Delhi) -> OutOfCoverage status."""
        url = reverse("submit_report")
        data = {
            "name": "Delhi Reporter",
            "email": "delhi@example.com",
            "latitude": "28.6139",
            "longitude": "77.2090",
            "issue_type": "poor_lighting",
            "description": "Streetlight not working on main road."
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        json_resp = response.json()
        self.assertTrue(json_resp.get("success"))

        report = UserReport.objects.get(id=json_resp["report_id"])
        self.assertEqual(report.coverage_status, "OutOfCoverage")

    def test_submit_report_with_photo(self):
        """Test submitting a report with a valid PNG image file."""
        url = reverse("submit_report")
        # 1x1 transparent PNG bytes
        png_bytes = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82'
        image_file = SimpleUploadedFile("pothole.png", png_bytes, content_type="image/png")

        data = {
            "name": "Photo Reporter",
            "email": "photo@example.com",
            "latitude": "9.9820",
            "longitude": "76.3000",
            "issue_type": "signal_failure",
            "description": "Traffic light blinker broken.",
            "photo": image_file
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        json_resp = response.json()
        self.assertTrue(json_resp.get("success"))

        report = UserReport.objects.get(id=json_resp["report_id"])
        self.assertTrue(bool(report.photo))

    def test_submit_report_validations(self):
        """Test various invalid inputs for report submission."""
        url = reverse("submit_report")

        # Missing name
        resp = self.client.post(url, {"name": "", "email": "a@b.com", "latitude": "9.9", "longitude": "76.2", "issue_type": "pothole", "description": "desc"})
        self.assertEqual(resp.status_code, 400)

        # Invalid email
        resp = self.client.post(url, {"name": "Test", "email": "not-an-email", "latitude": "9.9", "longitude": "76.2", "issue_type": "pothole", "description": "desc"})
        self.assertEqual(resp.status_code, 400)

        # Missing coordinates
        resp = self.client.post(url, {"name": "Test", "email": "test@example.com", "latitude": "", "longitude": "", "issue_type": "pothole", "description": "desc"})
        self.assertEqual(resp.status_code, 400)

        # Invalid issue type
        resp = self.client.post(url, {"name": "Test", "email": "test@example.com", "latitude": "9.9", "longitude": "76.2", "issue_type": "unknown_issue", "description": "desc"})
        self.assertEqual(resp.status_code, 400)

        # Missing description
        resp = self.client.post(url, {"name": "Test", "email": "test@example.com", "latitude": "9.9", "longitude": "76.2", "issue_type": "pothole", "description": ""})
        self.assertEqual(resp.status_code, 400)

    def test_approved_reports_api_and_privacy(self):
        """Test that /api/reports/approved/ returns only approved reports and never exposes email."""
        # 1. Create Pending report
        UserReport.objects.create(
            name="Pending User",
            email="pending_secret@example.com",
            latitude=9.9800,
            longitude=76.2900,
            issue_type="pothole",
            description="Pending pothole",
            status="Pending",
            coverage_status="InCoverage"
        )
        # 2. Create Rejected report
        UserReport.objects.create(
            name="Rejected User",
            email="rejected_secret@example.com",
            latitude=9.9700,
            longitude=76.2800,
            issue_type="other",
            description="Rejected issue",
            status="Rejected",
            coverage_status="InCoverage"
        )
        # 3. Create Approved report
        approved_report = UserReport.objects.create(
            name="Approved User",
            email="approved_secret@example.com",
            latitude=9.9900,
            longitude=76.3100,
            issue_type="unsafe_crossing",
            description="Zebra crossing faded near school.",
            status="Approved",
            coverage_status="InCoverage"
        )

        url = reverse("approved_reports_json")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn("reports", data)
        reports = data["reports"]

        # Only 1 report should be present (the approved one)
        self.assertEqual(len(reports), 1)
        r = reports[0]
        self.assertEqual(r["id"], approved_report.id)
        self.assertEqual(r["reported_by"], "Approved User")
        self.assertEqual(r["issue_type"], "Unsafe Pedestrian Crossing")
        self.assertEqual(r["description"], "Zebra crossing faded near school.")
        self.assertEqual(r["coverage_status"], "InCoverage")

        # CRITICAL: Verify email is NOT in response content at all
        self.assertNotIn("email", r)
        self.assertNotIn("approved_secret@example.com", response.content.decode("utf-8"))
        self.assertNotIn("pending_secret@example.com", response.content.decode("utf-8"))
        self.assertNotIn("rejected_secret@example.com", response.content.decode("utf-8"))

    def test_admin_bulk_actions(self):
        """Test Admin bulk approve and reject actions."""
        r1 = UserReport.objects.create(
            name="Report 1",
            email="r1@example.com",
            latitude=9.98,
            longitude=76.29,
            issue_type="pothole",
            description="Desc 1",
            status="Pending"
        )
        r2 = UserReport.objects.create(
            name="Report 2",
            email="r2@example.com",
            latitude=9.99,
            longitude=76.30,
            issue_type="poor_lighting",
            description="Desc 2",
            status="Pending"
        )

        admin_instance = UserReportAdmin(UserReport, AdminSite())
        request = self.factory.get("/admin/core/userreport/")
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(request)
        request.session.save()
        messages = FallbackStorage(request)
        setattr(request, '_messages', messages)

        # Test Approve bulk action
        queryset = UserReport.objects.filter(id__in=[r1.id, r2.id])
        admin_instance.approve_reports(request, queryset)
        r1.refresh_from_db()
        r2.refresh_from_db()
        self.assertEqual(r1.status, "Approved")
        self.assertEqual(r2.status, "Approved")

        # Test Reject bulk action
        admin_instance.reject_reports(request, queryset)
        r1.refresh_from_db()
        r2.refresh_from_db()
        self.assertEqual(r1.status, "Rejected")
        self.assertEqual(r2.status, "Rejected")
