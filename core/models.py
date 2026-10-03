from django.db import models


class Accident(models.Model):
    accident_id = models.CharField(max_length=50, unique=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    location = models.CharField(max_length=200, null=True, blank=True)

    latitude = models.FloatField()
    longitude = models.FloatField()

    date = models.DateField()
    time = models.TimeField()
    hour = models.IntegerField()
    day_of_week = models.CharField(max_length=20)
    is_weekend = models.BooleanField()

    road_type = models.CharField(max_length=100)
    lanes = models.IntegerField()
    traffic_signal = models.BooleanField()

    weather = models.CharField(max_length=50)
    visibility = models.IntegerField()
    temperature = models.FloatField()
    traffic_density = models.CharField(max_length=20)

    cause = models.CharField(max_length=200)
    accident_severity = models.CharField(max_length=20)

    vehicles_involved = models.IntegerField()
    casualties = models.IntegerField()
    is_peak_hour = models.BooleanField()

    # Calculated by our project, not taken from the CSV
    custom_risk_score = models.FloatField()

    cluster_id = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = "accidents"

    def __str__(self):
        return f"{self.accident_id} - {self.city}"


class HotspotCluster(models.Model):
    city = models.CharField(max_length=100)
    cluster_id = models.IntegerField()
    center_lat = models.FloatField()
    center_lng = models.FloatField()
    avg_risk_score = models.FloatField()
    risk_level = models.CharField(max_length=10)
    accident_count = models.IntegerField()

    area_name = models.CharField(
        max_length=200,
        blank=True,
        null=True
    )

    def __str__(self):
        return f"{self.city} - Cluster {self.cluster_id} ({self.risk_level})"


class UserReport(models.Model):
    """
    Community hazard report submitted by public users.
    Status can be reviewed, approved, or rejected by admin.
    """
    ISSUE_TYPES = [
        ('pothole', 'Pothole'),
        ('signal_failure', 'Traffic Signal Failure'),
        ('unsafe_crossing', 'Unsafe Pedestrian Crossing'),
        ('poor_lighting', 'Poor Street Lighting'),
        ('missing_signage', 'Missing Road Signage'),
        ('other', 'Other Safety Issue'),
    ]

    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
    ]

    COVERAGE_CHOICES = [
        ('InCoverage', 'InCoverage'),
        ('OutOfCoverage', 'OutOfCoverage'),
    ]

    name = models.CharField(max_length=100)
    email = models.EmailField()
    latitude = models.FloatField()
    longitude = models.FloatField()
    issue_type = models.CharField(max_length=50, choices=ISSUE_TYPES)
    description = models.TextField()
    photo = models.ImageField(upload_to='reports/', null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    coverage_status = models.CharField(max_length=20, choices=COVERAGE_CHOICES, default='InCoverage')
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "user_reports"
        ordering = ['-timestamp']

    def __str__(self):
        return f"Report #{self.id} - {self.get_issue_type_display()} by {self.name} ({self.status})"