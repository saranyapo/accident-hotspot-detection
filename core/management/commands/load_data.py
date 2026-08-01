import pandas as pd
from django.core.management.base import BaseCommand
from core.models import Accident

class Command(BaseCommand):
    help = "Load cleaned_accidents.csv into the Accident table"

    def handle(self, *args, **kwargs):
        df = pd.read_csv("data/cleaned_accidents.csv")

        Accident.objects.all().delete()
        self.stdout.write("Cleared existing Accident records.")

        records = []
        for _, row in df.iterrows():
            records.append(Accident(
                accident_id=int(row["accident_id"]),
                city=row["city"],
                state=row["state"],
                latitude=row["latitude"],
                longitude=row["longitude"],
                date=row["date"],
                time=row["time"],
                hour=int(row["hour"]),
                day_of_week=row["day_of_week"],
                is_weekend=bool(row["is_weekend"]),
                road_type=row["road_type"],
                lanes=int(row["lanes"]),
                traffic_signal=bool(row["traffic_signal"]),
                weather=row["weather"],
                visibility=row["visibility"],
                temperature=int(row["temperature"]),
                traffic_density=row["traffic_density"],
                cause=row["cause"],
                accident_severity=row["accident_severity"],
                vehicles_involved=int(row["vehicles_involved"]),
                casualties=int(row["casualties"]),
                is_peak_hour=bool(row["is_peak_hour"]),
                custom_risk_score=float(row["custom_risk_score"]),
            ))

        Accident.objects.bulk_create(records, batch_size=1000)
        self.stdout.write(self.style.SUCCESS(
            f"Loaded {len(records)} records into Accident table."
        ))