
# Create your views here.
import itertools
import time
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import UserSerializer, LoginSerializer,TagSerializer,ScheduleGroupSerializer,PLCConnectionSerializer,TagHistorySerializer
from .models import CustomUser,Tag,TagHistory,ScheduleGroup,ScheduleHistory,PLCConnection
from .Permissions import IsAdmin
from rest_framework.permissions import AllowAny
from django.shortcuts import render
from .modbus_client import ModbusConnection
from django_celery_beat.models import PeriodicTask, CrontabSchedule
import json
from pymodbus.client import ModbusTcpClient
import logging
from django.http import HttpResponse
from openpyxl import Workbook
from datetime import datetime, timedelta
from django.http import StreamingHttpResponse
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count
import csv
from io import StringIO

logger = logging.getLogger(__name__)
class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user_id = serializer.validated_data['user_id']
            password = serializer.validated_data['password']
            user = authenticate(request, username=user_id, password=password)
            if user:
                refresh = RefreshToken.for_user(user)
                return Response({
                    'refresh_token': str(refresh),
                    'token': str(refresh.access_token),
                    'user_id': user.user_id,
                    'role': user.role
                })
            return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# User List/Create View
class UserListCreateView(generics.ListCreateAPIView):
    queryset = CustomUser.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsAdmin]

# User Retrieve/Update/Delete View
class UserDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = CustomUser.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsAdmin]
    lookup_field = 'id'

# views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from .models import PLCConnection
from .serializers import PLCConnectionSerializer
from pymodbus.client import ModbusTcpClient
import logging

logger = logging.getLogger(__name__)

class ConnectView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        try:
            connection = PLCConnection.objects.first()
            serializer = PLCConnectionSerializer(connection) if connection else None
            return Response({
                'connection': serializer.data if serializer else None
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error fetching connection: {e}")
            return Response({'error': f"Failed to fetch connection: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request):
        serializer = PLCConnectionSerializer(data=request.data)
        if not serializer.is_valid():
            logger.error(f"Serializer errors: {serializer.errors}")
            return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        try:
            timeout = int(request.data.get('timeout', 10))
            retries = int(request.data.get('retries', 3))
            if timeout < 1 or timeout > 60:
                return Response({'error': 'Timeout must be between 1 and 60 seconds'}, status=status.HTTP_400_BAD_REQUEST)
            if retries < 0 or retries > 10:
                return Response({'error': 'Retries must be between 0 and 10'}, status=status.HTTP_400_BAD_REQUEST)

            # Test connection before saving
            client = ModbusTcpClient(
                host=request.data['ip_address'],
                port=request.data['port'],
                timeout=timeout
            )
            connection_successful = False
            for attempt in range(retries + 1):
                if client.connect():
                    connection_successful = True
                    logger.info(f"Connected to {request.data['ip_address']}:{request.data['port']} on attempt {attempt + 1}")
                    break
                else:
                    logger.warning(f"Connection attempt {attempt + 1} failed for {request.data['ip_address']}:{request.data['port']}")
                if attempt < retries:
                    time.sleep(1)

            if connection_successful:
                client.close()
                # Update or create the single PLC connection
                connection, created = PLCConnection.objects.update_or_create(
                    id=1,  # Ensure single record
                    defaults={
                        'ip_address': request.data['ip_address'],
                        'port': request.data['port']
                    }
                )
                return Response({
                    'message': f"Connection to {connection.ip_address}:{connection.port} saved successfully",
                    'connection': serializer.data
                }, status=status.HTTP_200_OK)
            else:
                logger.error(f"Failed to connect to {request.data['ip_address']}:{request.data['port']} after {retries + 1} attempts")
                return Response({'error': 'Failed to connect to Modbus server after retries'}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.error(f"Error saving connection: {e}")
            return Response({'error': f"Server error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class TagCreateView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request):
        serializer = TagSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response({'message': 'Tag added successfully'}, status=status.HTTP_201_CREATED)
        return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

# API view for listing and deleting tags
class TagListView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        tags = Tag.objects.all()
        serializer = TagSerializer(tags, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, tag_id=None):
        try:
            tag = Tag.objects.get(id=tag_id)
            tag.delete()
            return Response({'message': 'Tag deleted successfully'}, status=status.HTTP_200_OK)
        except Tag.DoesNotExist:
            return Response({'error': 'Tag not found'}, status=status.HTTP_404_NOT_FOUND)

    def patch(self, request, tag_id=None):
        try:
            tag = Tag.objects.get(id=tag_id)
            serializer = TagSerializer(tag, data=request.data, context={'request': request}, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response({'message': 'Tag updated successfully', 'data': serializer.data}, status=status.HTTP_200_OK)
            return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        except Tag.DoesNotExist:
            return Response({'error': 'Tag not found'}, status=status.HTTP_404_NOT_FOUND)
        
class ControlView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tags = Tag.objects.all()
        serializer = TagSerializer(tags, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        tag_id = request.data.get('tag_id')
        status_for_modbus = request.data.get('status')

        if tag_id is None or status_for_modbus is None:
            return Response({'error': 'Tag ID and status are required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Validate status_for_modbus
            status_for_modbus = int(status_for_modbus)
            if status_for_modbus not in [0, 1]:
                return Response({'error': 'Status must be 0 (OFF) or 1 (ON)'}, status=status.HTTP_400_BAD_REQUEST)

            tag = Tag.objects.get(id=tag_id)
            modbus_conn = ModbusConnection(timeout=10, retries=3)  # Configurable timeout and retries
            client = modbus_conn.get_client()

            if not client or not client.is_socket_open():
                modbus_conn.close()
                return Response({'error': 'No active Modbus connection or connection closed'}, status=status.HTTP_400_BAD_REQUEST)

            # Write to PLC with retry logic
            max_attempts = 3
            for attempt in range(max_attempts):
                try:
                    client.write_coil(int(tag.tag_value), bool(status_for_modbus))
                    break  # Success, exit retry loop
                except Exception as write_error:
                    logger.error(f"Write attempt {attempt + 1} failed: {str(write_error)}")
                    if attempt < max_attempts - 1:
                        time.sleep(1)  # Wait before retrying
                        # Reconnect if socket is closed
                        modbus_conn.close()
                        client = modbus_conn.get_client()
                        if not client or not client.is_socket_open():
                            return Response({'error': 'Failed to reconnect to Modbus server'}, status=status.HTTP_400_BAD_REQUEST)
                    else:
                        modbus_conn.close()
                        return Response({'error': f'Modbus write failed: {str(write_error)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # Update tag status
            tag.status = status_for_modbus
            tag.save()

            # Log to history
            TagHistory.objects.create(
                tag=tag,
                status=status_for_modbus,
                user=request.user
            )

            modbus_conn.close()  # Ensure connection is closed after operation
            return Response({'message': 'Tag status updated successfully'}, status=status.HTTP_200_OK)

        except Tag.DoesNotExist:
            return Response({'error': 'Tag not found'}, status=status.HTTP_404_NOT_FOUND)
        except ValueError as ve:
            return Response({'error': f'Invalid tag value or status: {str(ve)}'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Unexpected error in ControlView: {e}")
            return Response({'error': f'Unexpected error: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class ScheduleView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request, schedule_id=None):
        if schedule_id:
            try:
                schedule = ScheduleGroup.objects.get(id=schedule_id)
                serializer = ScheduleGroupSerializer(schedule)
                return Response(serializer.data, status=status.HTTP_200_OK)
            except ScheduleGroup.DoesNotExist:
                return Response({'error': 'Schedule not found'}, status=status.HTTP_404_NOT_FOUND)
        schedules = ScheduleGroup.objects.all()
        serializer = ScheduleGroupSerializer(schedules, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = ScheduleGroupSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            schedule = serializer.save()

            # Create Celery tasks for ON and OFF times
            days = schedule.days
            on_time = schedule.on_time
            off_time = schedule.off_time

            # Create Crontab schedules
            on_crontab, _ = CrontabSchedule.objects.get_or_create(
                minute=on_time.minute,
                hour=on_time.hour,
                day_of_week=','.join([k for k, v in days.items() if v]),
                day_of_month='*',
                month_of_year='*',
                timezone='Asia/Kolkata'
            )
            off_crontab, _ = CrontabSchedule.objects.get_or_create(
                minute=off_time.minute,
                hour=off_time.hour,
                day_of_week=','.join([k for k, v in days.items() if v]),
                day_of_month='*',
                month_of_year='*',
                timezone='Asia/Kolkata'
            )

            # Create PeriodicTasks
            PeriodicTask.objects.create(
                crontab=on_crontab,
                name=f"ON_{schedule.id}_{schedule.name}",
                task='utility_app.tasks.execute_schedule',
                args=json.dumps([schedule.id, True])
            )
            PeriodicTask.objects.create(
                crontab=off_crontab,
                name=f"OFF_{schedule.id}_{schedule.name}",
                task='utility_app.tasks.execute_schedule',
                args=json.dumps([schedule.id, False])
            )

            return Response({'message': 'Schedule created successfully'}, status=status.HTTP_201_CREATED)
        return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, schedule_id=None):
        try:
            schedule = ScheduleGroup.objects.get(id=schedule_id)
            serializer = ScheduleGroupSerializer(schedule, data=request.data, partial=True, context={'request': request})
            if serializer.is_valid():
                schedule = serializer.save()

                # If days, on_time, or off_time are updated, recreate Celery tasks
                if any(key in request.data for key in ['days', 'on_time', 'off_time']):
                    # Delete existing tasks
                    PeriodicTask.objects.filter(name__startswith=f"ON_{schedule.id}_").delete()
                    PeriodicTask.objects.filter(name__startswith=f"OFF_{schedule.id}_").delete()

                    # Create new tasks
                    days = schedule.days
                    on_time = schedule.on_time
                    off_time = schedule.off_time

                    on_crontab, _ = CrontabSchedule.objects.get_or_create(
                        minute=on_time.minute,
                        hour=on_time.hour,
                        day_of_week=','.join([k for k, v in days.items() if v]),
                        day_of_month='*',
                        month_of_year='*',
                        timezone='Asia/Kolkata'
                    )
                    off_crontab, _ = CrontabSchedule.objects.get_or_create(
                        minute=off_time.minute,
                        hour=off_time.hour,
                        day_of_week=','.join([k for k, v in days.items() if v]),
                        day_of_month='*',
                        month_of_year='*',
                        timezone='Asia/Kolkata'
                    )

                    PeriodicTask.objects.create(
                        crontab=on_crontab,
                        name=f"ON_{schedule.id}_{schedule.name}",
                        task='utility_app.tasks.execute_schedule',
                        args=json.dumps([schedule.id, True])
                    )
                    PeriodicTask.objects.create(
                        crontab=off_crontab,
                        name=f"OFF_{schedule.id}_{schedule.name}",
                        task='utility_app.tasks.execute_schedule',
                        args=json.dumps([schedule.id, False])
                    )

                return Response({'message': 'Schedule updated successfully'}, status=status.HTTP_200_OK)
            return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        except ScheduleGroup.DoesNotExist:
            return Response({'error': 'Schedule not found'}, status=status.HTTP_404_NOT_FOUND)

    def delete(self, request, schedule_id=None):
        try:
            schedule = ScheduleGroup.objects.get(id=schedule_id)
            # Delete associated Celery tasks
            PeriodicTask.objects.filter(name__startswith=f"ON_{schedule.id}_").delete()
            PeriodicTask.objects.filter(name__startswith=f"OFF_{schedule.id}_").delete()
            schedule.delete()
            return Response({'message': 'Schedule deleted successfully'}, status=status.HTTP_200_OK)
        except ScheduleGroup.DoesNotExist:
            return Response({'error': 'Schedule not found'}, status=status.HTTP_404_NOT_FOUND)
        

class TagHistoryReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Get query parameters
        department = request.query_params.get('department', '')
        date_filter = request.query_params.get('date_filter', '')
        start_date = request.query_params.get('start_date', '')
        end_date = request.query_params.get('end_date', '')

        # Base queryset
        tag_history = TagHistory.objects.all()

        # Filter by department if provided
        if department:
            tag_history = tag_history.filter(tag__department=department)

        # Filter by date
        if date_filter == 'custom' and start_date and end_date:
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d')
                end_date = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)  # Include end date
                tag_history = tag_history.filter(timestamp__range=[start_date, end_date])
            except ValueError:
                return Response({'error': 'Invalid date format'}, status=status.HTTP_400_BAD_REQUEST)
        elif date_filter == 'last_week':
            start_date = datetime.now() - timedelta(days=7)
            tag_history = tag_history.filter(timestamp__gte=start_date)
        elif date_filter == 'last_month':
            start_date = datetime.now() - timedelta(days=30)
            tag_history = tag_history.filter(timestamp__gte=start_date)
        elif date_filter == 'last_six_months':
            start_date = datetime.now() - timedelta(days=180)
            tag_history = tag_history.filter(timestamp__gte=start_date)

        # Order by timestamp descending
        tag_history = tag_history.order_by('-timestamp')

        # Serialize data
        serializer = TagHistorySerializer(tag_history, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    
    
class TagHistoryExportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Get query parameters (same as TagHistoryReportView)
        department = request.query_params.get('department', '')
        date_filter = request.query_params.get('date_filter', '')
        start_date = request.query_params.get('start_date', '')
        end_date = request.query_params.get('end_date', '')

        # Base queryset
        tag_history = TagHistory.objects.all()

        # Filter by department if provided
        if department:
            tag_history = tag_history.filter(tag__department=department)

        # Filter by date
        if date_filter == 'custom' and start_date and end_date:
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d')
                end_date = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
                tag_history = tag_history.filter(timestamp__range=[start_date, end_date])
            except ValueError:
                return Response({'error': 'Invalid date format'}, status=status.HTTP_400_BAD_REQUEST)
        elif date_filter == 'last_week':
            start_date = datetime.now() - timedelta(days=7)
            tag_history = tag_history.filter(timestamp__gte=start_date)
        elif date_filter == 'last_month':
            start_date = datetime.now() - timedelta(days=30)
            tag_history = tag_history.filter(timestamp__gte=start_date)
        elif date_filter == 'last_six_months':
            start_date = datetime.now() - timedelta(days=180)
            tag_history = tag_history.filter(timestamp__gte=start_date)

        # Order by timestamp descending
        tag_history = tag_history.order_by('-timestamp')

        # Create CSV response
        def stream_csv():
            output = StringIO()
            writer = csv.writer(output)
            # Write CSV header
            writer.writerow(['Tag Name', 'Tag ID', 'Department', 'Status', 'Timestamp', 'User ID'])

            # Write CSV rows
            for item in tag_history:
                writer.writerow([
                    item.tag.tag_name,
                    item.tag.tag_id,
                    item.tag.department,
                    'ON' if item.status else 'OFF',
                    item.timestamp.isoformat(),
                    item.user.id
                ])
                # Yield the output in chunks
                yield output.getvalue()
                output.seek(0)
                output.truncate(0)

        # Set response headers for CSV download
        response = StreamingHttpResponse(stream_csv(), content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="tag_history_report.csv"'
        return response    

# New API View for Departments
class DepartmentListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        departments = Tag.objects.values_list('department', flat=True).distinct()
        return Response(list(departments), status=status.HTTP_200_OK)


class TagEditView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def put(self, request, tag_id):
        try:
            tag = Tag.objects.get(id=tag_id)
            serializer = TagSerializer(tag, data=request.data, partial=True, context={'request': request})
            if serializer.is_valid():
                serializer.save()
                return Response({'message': 'Tag updated successfully'}, status=status.HTTP_200_OK)
            return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        except Tag.DoesNotExist:
            return Response({'error': 'Tag not found'}, status=status.HTTP_404_NOT_FOUND)
        
        
class ActiveTagsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        active_tags = Tag.objects.filter(status=True)
        serializer = TagSerializer(active_tags, many=True)
        return Response(serializer.data)

class ActiveSchedulesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        active_schedules = ScheduleGroup.objects.filter(is_active=True)
        data = []
        for schedule in active_schedules:
            data.append({
                'name': schedule.name,
                'department': schedule.department,
                'tags': [tag.tag_name for tag in schedule.tags.all()],
                'days': schedule.days,
                'on_time': schedule.on_time.strftime('%H:%M:%S'),
                'off_time': schedule.off_time.strftime('%H:%M:%S')
            })
        return Response(data)

class TopTagsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        one_week_ago = timezone.now() - timedelta(days=7)
        tag_histories = TagHistory.objects.filter(
            timestamp__gte=one_week_ago
        ).select_related('tag').order_by('tag__tag_id', 'timestamp')

        tag_durations = {}
        current_time = timezone.now()

        for tag_id, group in itertools.groupby(tag_histories, key=lambda x: x.tag.tag_id):
            group = list(group)
            total_duration = timedelta()

            for i in range(len(group)):
                if group[i].status:  # "On" event
                    start_time = group[i].timestamp
                    # Find the next "Off" event or use current time if still "On"
                    end_time = current_time if i + 1 == len(group) or group[i + 1].status else group[i + 1].timestamp
                    duration = end_time - start_time
                    total_duration += duration

            if total_duration.total_seconds() > 0:
                tag = group[0].tag
                # Convert total duration to minutes
                total_minutes = total_duration.total_seconds() / 60
                tag_durations[tag_id] = {
                    'tag_name': tag.tag_name,
                    'tag_id': tag.tag_id,
                    'department': tag.department,
                    'on_duration_minutes': round(total_minutes, 2)  # Round to 2 decimal places
                }

        # Sort by duration and get top 5
        top_tags = sorted(
            tag_durations.values(),
            key=lambda x: x['on_duration_minutes'],
            reverse=True
        )[:5]

        return Response(top_tags)


def control_page(request):
    return render(request, 'controls.html')

def home_view(request):
    return render(request, 'home.html')

# User Page Template View
def user_page_view(request):
    return render(request, 'user_page.html')

def create_user_view(request):
    return render(request, 'create_user.html')

# Login Page Template View
def login_page_view(request):
    return render(request, 'login.html')

def connection_view(request):
    return render(request, 'connection.html')

def config_view(request):
    return render(request, 'config.html')

def add_tag_view(request):
    return render(request, 'add_tag.html')

def scheduled_view(request):
    return render(request, 'scheduled.html')

# Render add schedule page
def add_schedule_view(request):
    return render(request, 'add_schedule.html')

def update_schedule_view(request, schedule_id):
    return render(request, 'update_schedule.html', {'schedule_id': schedule_id})

def report_view(request):
    return render(request, 'report.html')