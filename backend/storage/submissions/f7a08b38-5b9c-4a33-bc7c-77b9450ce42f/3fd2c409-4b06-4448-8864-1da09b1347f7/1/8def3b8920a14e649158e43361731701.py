from datetime import datetime
from typing import Dict


class VideoConsultation:
    def __init__(self, patient_id: str, doctor_id: str):
        self.patient_id = patient_id
        self.doctor_id = doctor_id
        self.status = "scheduled"
        self.created_at = datetime.utcnow()

    def start(self) -> Dict[str, str]:
        self.status = "in_progress"

        return {
            "patient_id": self.patient_id,
            "doctor_id": self.doctor_id,
            "status": self.status,
        }

    def end(self) -> Dict[str, str]:
        self.status = "completed"

        return {
            "patient_id": self.patient_id,
            "doctor_id": self.doctor_id,
            "status": self.status,
        }


def create_consultation(patient_id: str, doctor_id: str) -> VideoConsultation:
    if not patient_id:
        raise ValueError("patient_id is required")

    if not doctor_id:
        raise ValueError("doctor_id is required")

    return VideoConsultation(
        patient_id=patient_id,
        doctor_id=doctor_id,
    )