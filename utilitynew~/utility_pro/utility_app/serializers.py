# utility_app/serializers.py
from rest_framework import serializers
from .models import CustomUser,Tag,ScheduleGroup,ScheduleHistory,PLCConnection,TagHistory

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'user_id', 'password', 'role']
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        user = CustomUser.objects.create_user(
            username=validated_data['username'],
            user_id=validated_data['user_id'],
            password=validated_data['password'],
            role=validated_data['role']
        )
        return user

    def update(self, instance, validated_data):
        instance.username = validated_data.get('username', instance.username)
        instance.user_id = validated_data.get('user_id', instance.user_id)
        instance.role = validated_data.get('role', instance.role)
        if 'password' in validated_data and validated_data['password']:
            instance.set_password(validated_data['password'])
        instance.save()
        return instance

class LoginSerializer(serializers.Serializer):
    user_id = serializers.CharField()
    password = serializers.CharField(write_only=True)
    
class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['id', 'tag_name', 'tag_value', 'tag_id', 'department','status']

    def create(self, validated_data):
        # Add the user who created the tag
        user = self.context['request'].user
        tag = Tag.objects.create(created_by=user, **validated_data)
        return tag

    def update(self, instance, validated_data):
        # Update the tag instance with validated data
        instance.tag_name = validated_data.get('tag_name', instance.tag_name)
        instance.tag_value = validated_data.get('tag_value', instance.tag_value)
        instance.tag_id = validated_data.get('tag_id', instance.tag_id)
        instance.department = validated_data.get('department', instance.department)
        # instance.status = validated_data.get('status', instance.status)
        instance.save()
        return instance

    
class ScheduleGroupSerializer(serializers.ModelSerializer):
    tags = TagSerializer(many=True, read_only=True)
    tags_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True)

    class Meta:
        model = ScheduleGroup
        fields = ['id', 'name', 'department', 'tags', 'tags_ids', 'days', 'on_time', 'off_time', 'is_active', 'created_at', 'created_by']
        read_only_fields = ['created_by']

    def create(self, validated_data):
        tags_ids = validated_data.pop('tags_ids', [])
        validated_data.pop('created_by', None)
        user = self.context['request'].user
        schedule = ScheduleGroup.objects.create(created_by=user, **validated_data)
        schedule.tags.set(tags_ids)
        return schedule

    def update(self, instance, validated_data):
        tags_ids = validated_data.pop('tags_ids', None)
        validated_data.pop('created_by', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if tags_ids is not None:
            instance.tags.set(tags_ids)
        return instance
    
class PLCConnectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PLCConnection
        fields = ['ip_address', 'port']
        


class TagHistorySerializer(serializers.ModelSerializer):
    tag_name = serializers.CharField(source='tag.tag_name')
    tag_id = serializers.CharField(source='tag.tag_id')
    department = serializers.CharField(source='tag.department')
    user_id = serializers.IntegerField(source='user.id')

    class Meta:
        model = TagHistory
        fields = ['id', 'tag_name', 'tag_id', 'department', 'status', 'timestamp', 'user_id']