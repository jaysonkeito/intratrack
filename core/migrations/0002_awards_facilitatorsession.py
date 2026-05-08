from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ChampionshipAward',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('award_type', models.CharField(choices=[('mvp', 'MVP'), ('potg', 'Player of the Game')], max_length=10)),
                ('player_name', models.CharField(max_length=100)),
                ('college', models.CharField(blank=True, choices=[('CAF', 'College of Agriculture and Forestry'), ('CAS', 'College of Arts and Sciences'), ('CBA', 'College of Business Administration'), ('CIT', 'College of Industrial Technology'), ('CTED', 'College of Teacher Education'), ('CCJE', 'College of Criminal Justice Education')], max_length=10, null=True)),
                ('note', models.CharField(blank=True, help_text='Optional note, e.g. stats summary', max_length=200)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='awards', to='core.category')),
            ],
            options={'ordering': ['award_type'], 'unique_together': {('category', 'award_type')}},
        ),
        migrations.CreateModel(
            name='FacilitatorSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('session_key', models.CharField(max_length=40, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('last_seen', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='facilitator_sessions', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['created_at']},
        ),
    ]
