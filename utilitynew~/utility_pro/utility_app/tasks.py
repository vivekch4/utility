from celery import shared_task
from django.utils import timezone
from .models import ScheduleGroup, ScheduleHistory, Tag, PLCConnection
from pymodbus.client import ModbusTcpClient
import logging
import time

logger = logging.getLogger(__name__)

@shared_task
def execute_schedule(schedule_id, status):
    try:
        # Fetch the schedule
        schedule = ScheduleGroup.objects.get(id=schedule_id)
        if not schedule.is_active:
            logger.info(f"Schedule {schedule.name} is inactive, skipping.")
            return

        # Fetch PLC connection details from the database
        plc = PLCConnection.objects.first()
        if not plc:
            logger.error("No PLC connection found in the database.")
            return

        # Initialize Modbus client with timeout and retries
        timeout = 10  # Default timeout in seconds
        retries = 3   # Default number of retries
        client = ModbusTcpClient(
            host=plc.ip_address,
            port=plc.port,
            timeout=timeout
        )

        # Attempt to connect with retries
        connection_successful = False
        for attempt in range(retries + 1):
            try:
                if client.connect():
                    logger.info(f"Connected to Modbus server at {plc.ip_address}:{plc.port} on attempt {attempt + 1}")
                    connection_successful = True
                    break
                else:
                    logger.warning(f"Connection attempt {attempt + 1} failed for {plc.ip_address}:{plc.port}")
            except Exception as conn_error:
                logger.error(f"Connection attempt {attempt + 1} error: {str(conn_error)}")
            if attempt < retries:
                time.sleep(1)  # Wait before retrying

        if not connection_successful:
            logger.error(f"Failed to connect to Modbus server at {plc.ip_address}:{plc.port} after {retries + 1} attempts")
            return

        try:
            # Iterate through tags in the schedule and write to PLC
            for tag in schedule.tags.all():
                try:
                    client.write_coil(int(tag.tag_value), bool(status))
                    tag.status = status
                    tag.save()
                    ScheduleHistory.objects.create(
                        schedule_group=schedule,
                        tag=tag,
                        status=status,
                        user=None,
                    
                    )
                    logger.info(f"Tag {tag.tag_name} set to {'ON' if status else 'OFF'} for schedule {schedule.name}")
                except Exception as tag_error:
                    logger.error(f"Failed to write to tag {tag.tag_name} (value: {tag.tag_value}): {tag_error}")
                    continue  # Continue with the next tag on failure
        finally:
            # Always close the Modbus connection
            if client and client.is_socket_open():
                client.close()
                logger.info("Modbus connection closed after schedule execution")

    except ScheduleGroup.DoesNotExist:
        logger.error(f"Schedule with ID {schedule_id} does not exist.")
    except Exception as e:
        logger.error(f"Error executing schedule {schedule_id}: {e}")