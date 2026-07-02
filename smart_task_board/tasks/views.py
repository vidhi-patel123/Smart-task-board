import hashlib
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
import json
from datetime import timedelta
from .models import Task, Priority

CRYPTIC_HINTS = [
    "The stars are not aligned for this task.",
    "A shadow blocks the path forward.",
    "The oracle whispers: 'Not yet, wanderer.'",
    "The task resists — echoes of past failures linger.",
    "The gate is shut. Seek the forgotten key.",
    "Time is a river flowing backwards here.",
    "The task speaks: 'I am not ready to be tamed.'",
    "Beware the second attempt — it knows your name.",
]

# priority = Priority.objects.get(name="high")

# task.objects.create(
#     title = "Django project",
#     priority=priority,
#     estimated_time=30
# )


def get_cryptic_hint(task):
    # converts task properties into an MD5 hash, select a consistent cryptic message
    seed = f"{task.id}{task.title}{task.completion_attempts}"
    idx = int(hashlib.md5(seed.encode()).hexdigest(), 16) % len(CRYPTIC_HINTS)
    return CRYPTIC_HINTS[idx]


def index(request):
    tasks = Task.objects.all()
    # Refresh statuses
    for task in tasks:
        task.is_locked()
        task.is_expired()
    tasks = Task.objects.all()
    return render(request, 'tasks/index.html', {'tasks': tasks})



@csrf_exempt
@require_POST
def add_task(request):
    try:
        data = json.loads(request.body)

        title = data.get('title', '').strip()
        priority_name = data.get('priority', 'medium')
        estimated_time = int(data.get('estimated_time', 30))

        if not title:
            return JsonResponse({
                'success': False,
                'error': 'Title is required.'
            })

        if priority_name not in ['low', 'medium', 'high']:
            return JsonResponse({
                'success': False,
                'error': 'Invalid priority.'
            })

        if estimated_time <= 0:
            return JsonResponse({
                'success': False,
                'error': 'Estimated time must be positive.'
            })

        # Convert string to Priority instance
        priority = Priority.objects.get(name=priority_name)

        now = timezone.now()
        two_mins_ago = now - timedelta(minutes=2)
        recent_count = Task.objects.filter(created_at__gte=two_mins_ago).count()

        # Rule 2: If 3 tasks added within 2 minutes, 4th gets locked for 5 minutes
        is_locked_task = recent_count == 3
        # is_locked_task = recent_count >= 3
        locked_until = now + timedelta(minutes=5) if is_locked_task else None

        # Rule 3: Odd minute tasks have a deadline
        current_minute = now.minute
        is_odd = current_minute % 2 != 0
        deadline = now + timedelta(minutes=estimated_time) if is_odd else None

        task = Task.objects.create(
            title=title,
            priority=priority,  # Priority object, not string
            estimated_time=estimated_time,
            created_at=now,
            status='locked' if is_locked_task else 'pending',
            locked_until=locked_until,
            is_odd_minute_task=is_odd,
            deadline=deadline,
        )

        return JsonResponse({
            'success': True,
            'task': serialize_task(task),
            'message': (
                f'Task locked for 5 minutes (rapid creation detected)!'
                if is_locked_task else
                f'Task created at odd minute — must complete within {estimated_time} mins!'
                if is_odd else
                'Task added successfully!'
            )
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@csrf_exempt
@require_POST
def complete_task(request, task_id):
    task = get_object_or_404(Task, id=task_id)

    # Refresh status
    task.is_locked()
    task.is_expired()
    task.refresh_from_db()

    if task.status == 'completed':
        return JsonResponse({'success': False, 'hint': '✨ This journey has already reached its end.'})

    if task.status == 'locked':
        secs = task.seconds_until_unlock()
        return JsonResponse({
            'success': False,
            'hint': '🔒 The task sleeps in an iron cage — patience is your only key.'
        })

    if task.status == 'expired':
        return JsonResponse({
            'success': False,
            # 'error': 'Task has expired.',
            'hint': '⏳ Time dissolved before the deed was done.'
        })

    if task.is_odd_minute_task and task.deadline:
        if timezone.now() > task.deadline:
            task.status = 'expired'
            task.save(update_fields=['status'])
            return JsonResponse({
                'success': False,
                'error': 'Deadline passed!',
                'hint': '⏳ The hourglass ran dry before the sand could be gathered.'
            })

    # ── Rule 1: High priority blocked until ≥1 Low task completed ─────────────
    if task.priority.name == 'high':
        low_completed = Task.objects.filter(
            priority_name='low',
            status='completed'
        ).exists()

        if not low_completed:
            task.completion_attempts += 1
            task.save(update_fields=['completion_attempts'])

            return JsonResponse({
                'success': False,
                'hint': f'🌀 {get_cryptic_hint(task)}'
            })

   # Rule 4: Hidden refusal logic
    refusal_seed = (
        len(task.title) * task.estimated_time +
        task.completion_attempts
    ) % 7

    priority_weight = {
        'low': 1,
        'medium': 2,
        'high': 3
    }[task.priority.name]

    if refusal_seed == priority_weight and task.completion_attempts < 3:
        task.completion_attempts += 1
        task.save(update_fields=['completion_attempts'])

        return JsonResponse({
            'success': False,
            'hint': f'🌀 {get_cryptic_hint(task)}'
        })

    # If hidden logic does NOT trigger, complete the task
    task.status = 'completed'
    task.save(update_fields=['status'])

    return JsonResponse({
        'success': True,
        'message': '✅ Task completed!',
        'task': serialize_task(task)
    })




@csrf_exempt
@require_POST
def delete_task(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    task.delete()
    return JsonResponse({'success': True})


@require_GET
def task_status(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    task.is_locked()
    task.is_expired()
    task.refresh_from_db()
    return JsonResponse({'task': serialize_task(task)})


@require_GET
def all_tasks(request):
    tasks = Task.objects.all()
    for t in tasks:
        t.is_locked()
        t.is_expired()
    tasks = Task.objects.all()
    return JsonResponse({'tasks': [serialize_task(t) for t in tasks]})


def serialize_task(task):
    return {
        'id': task.id,
        'title': task.title,
        'priority': task.priority.name,
        'estimated_time': task.estimated_time,
        'created_at': task.created_at.isoformat(),
        'status': task.status,
        'locked_until': task.locked_until.isoformat() if task.locked_until else None,
        'deadline': task.deadline.isoformat() if task.deadline else None,
        'is_odd_minute_task': task.is_odd_minute_task,
        'completion_attempts': task.completion_attempts,
        'seconds_until_unlock': task.seconds_until_unlock(),
        'seconds_until_deadline': task.seconds_until_deadline(),
    }
