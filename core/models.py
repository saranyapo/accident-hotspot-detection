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