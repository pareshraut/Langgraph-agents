import os, re, json
import pandas as pd
from datetime import datetime
from typing import Literal

from langchain_openai import ChatOpenAI
from langchain_core.pydantic_v1 import BaseModel, Field, validator
from langchain_core.tools import tool
from langchain_core.prompts.chat import ChatPromptTemplate
from langgraph_supervisor import create_handoff_tool, create_supervisor
from langgraph.prebuilt.chat_agent_executor import create_react_agent

# Instantiate the shared LLM
llm = ChatOpenAI(model="gpt-4o", temperature=0.0)

# --- Data Models ---
class DateModel(BaseModel):
    date: str = Field(..., pattern=r'^\d{2}-\d{2}-\d{4}$')

    @validator('date')
    def validate_date_format(cls, v):
        """Ensure date is in DD-MM-YYYY format."""
        if not re.match(r'^\d{2}-\d{2}-\d{4}$', v):
            raise ValueError("Date must be 'DD-MM-YYYY'")
        return v

class DateTimeModel(BaseModel):
    date: str = Field(..., pattern=r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$')

    @validator('date')
    def validate_datetime_format(cls, v):
        """Ensure datetime is in YYYY-MM-DD HH:MM format."""
        if not re.match(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$', v):
            raise ValueError("Datetime must be 'YYYY-MM-DD HH:MM'")
        return v

class IdentificationNumberModel(BaseModel):
    id: int = Field(..., pattern=r'^\d{7,8}$')

    @validator('id')
    def validate_id_format(cls, v):
        """Ensure ID is a 7 or 8 digit integer."""
        if not re.match(r'^\d{7,8}$', str(v)):
            raise ValueError("ID must be 7 or 8 digits")
        return v

# --- Tools ---
@tool
def check_availability_by_doctor(desired_date: DateModel, doctor_name: Literal[
    'kevin anderson','robert martinez','susan davis','daniel miller',
    'sarah wilson','michael green','lisa brown','jane smith',
    'emily johnson','john doe'
]):
    """
    Check availability for a given doctor on a specified date.
    Reads `availability.csv` and returns available time slots.
    """
    df = pd.read_csv('availability.csv')
    df['slot_time'] = df['date_slot'].str.split(' ').str[1]
    slots = df.query(
        "date_slot.str.startswith(@desired_date.date) and doctor_name==@doctor_name and is_available"
    ).slot_time.tolist()
    return "No availability" if not slots else f"Available slots: {', '.join(slots)}"

@tool
def check_availability_by_specialization(desired_date: DateModel, specialization: Literal[
    'general_dentist','cosmetic_dentist','prosthodontist','pediatric_dentist',
    'emergency_dentist','oral_surgeon','orthodontist'
]):
    """
    Check availability by specialization for a specified date.
    Groups available slots by doctor and lists them.
    """
    df = pd.read_csv('availability.csv')
    df['slot_time'] = df['date_slot'].str.split(' ').str[1]
    grouped = df.query(
        "date_slot.str.startswith(@desired_date.date) and specialization==@specialization and is_available"
    ).groupby('doctor_name').slot_time.apply(list)
    if grouped.empty:
        return "No availability"
    return '\n'.join(f"{dr}: {', '.join(times)}" for dr, times in grouped.items())

@tool
def set_appointment(desired_date: DateTimeModel, id_number: IdentificationNumberModel, doctor_name: Literal[
    'kevin anderson','robert martinez','susan davis','daniel miller',
    'sarah wilson','michael green','lisa brown','jane smith',
    'emily johnson','john doe'
]):
    """
    Book an appointment: marks the slot as unavailable and assigns patient ID.
    """
    df = pd.read_csv('availability.csv')
    fmt = datetime.strptime(desired_date.date, "%Y-%m-%d %H:%M").strftime("%d-%m-%Y %H.%M")
    mask = (df.date_slot==fmt) & (df.doctor_name==doctor_name) & df.is_available
    if not mask.any():
        return "No slot available"
    df.loc[mask, ['is_available','patient_to_attend']] = [False, id_number.id]
    df.to_csv('availability.csv', index=False)
    return "Successfully booked"

@tool
def cancel_appointment(date: DateTimeModel, id_number: IdentificationNumberModel, doctor_name: Literal[
    'kevin anderson','robert martinez','susan davis','daniel miller',
    'sarah wilson','michael green','lisa brown','jane smith',
    'emily johnson','john doe'
]):
    """
    Cancel an appointment: frees the slot and clears patient ID.
    """
    df = pd.read_csv('availability.csv')
    mask = (
        (df.date_slot==date.date) &
        (df.patient_to_attend==id_number.id) &
        (df.doctor_name==doctor_name)
    )
    if not mask.any():
        return "No matching appointment found"
    df.loc[mask, ['is_available','patient_to_attend']] = [True, None]
    df.to_csv('availability.csv', index=False)
    return "Successfully canceled"

@tool
def reschedule_appointment(old_date: DateTimeModel, new_date: DateTimeModel, id_number: IdentificationNumberModel, doctor_name: Literal[
    'kevin anderson','robert martinez','susan davis','daniel miller',
    'sarah wilson','michael green','lisa brown','jane smith',
    'emily johnson','john doe'
]):
    """
    Reschedule an appointment by canceling the old slot and booking a new one.
    """
    cancel_appointment.invoke({'date': old_date, 'id_number': id_number, 'doctor_name': doctor_name})
    return set_appointment.invoke({'desired_date': new_date, 'id_number': id_number, 'doctor_name': doctor_name})

# --- Create specialized agents ---
info_agent = create_react_agent(
    name="info_agent",
    model=llm,
    tools=[check_availability_by_doctor, check_availability_by_specialization],
    prompt=ChatPromptTemplate.from_messages([
        ("system", "You provide doctor availability info, ask for missing details."),
        ("placeholder", "{messages}")
    ])
)

booking_agent = create_react_agent(
    name="booking_agent",
    model=llm,
    tools=[set_appointment, cancel_appointment, reschedule_appointment],
    prompt=ChatPromptTemplate.from_messages([
        ("system", "You handle booking tasks: set, cancel, reschedule appointments."),
        ("placeholder", "{messages}")
    ])
)

# --- Supervisor Setup ---
supervisor_prompt = "You are a supervisor that routes between 'info_agent' and 'booking_agent'. When done reply FINISH."

graph = create_supervisor(
    agents=[info_agent, booking_agent],
    model=llm,
    prompt=supervisor_prompt
)