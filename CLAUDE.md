# AIS MCP — STU Academic Information System

MCP-сервер для `is.stuba.sk` (STU). Даёт Claude и другим AI-агентам доступ к расписанию, оценкам, почте, экзаменам, финансам и другим функциям АИС.

## Запуск

```bash
# Активировать venv
source .venv/bin/activate

# Запустить сервер вручную (stdio)
AIS_USERNAME=xlogin AIS_PASSWORD=yourpass python -m ais_mcp

# Тесты парсеров
python -m pytest tests/ -v

# Установка зависимостей
pip install -e .
```

## Конфигурация

Создай `.env` (уже в `.gitignore`):
```
AIS_USERNAME=xsavin
AIS_PASSWORD=...
# Опционально — пропустить авто-детект:
# AIS_DEFAULT_STUDIUM=192844
# AIS_DEFAULT_OBDOBI=706
```

Cookie кешируется в `~/.cache/ais-mcp/cookies.json` (mode 600). MCP сам перелогинивается при истечении сессии.

## Подключение

| Инструмент | Статус | Конфиг |
|-----------|--------|--------|
| Claude Code | ✅ | `~/.claude.json` (user scope) |
| OpenCode | ✅ | Читает из `~/.claude.json` автоматически |
| Codex CLI | ✅ | `~/.codex/config.toml` (global) |

Добавить заново (если слетело):
```bash
# Claude Code
claude mcp add ais /home/dimka/Development/AIS_MCP/.venv/bin/python \
  -a '-m' -a 'ais_mcp' \
  -e AIS_USERNAME=xsavin -e AIS_PASSWORD=... --scope user

# Codex
codex mcp add ais \
  --env AIS_USERNAME=xsavin --env AIS_PASSWORD=... \
  -- /home/dimka/Development/AIS_MCP/.venv/bin/python -m ais_mcp
```

## Структура

```
src/ais_mcp/
├── server.py      — FastMCP, регистрация 52 tools
├── session.py     — HTTP-сессия, авто-логин, cookie cache
├── context.py     — авто-детект studium/obdobi/rozvrh_student
├── parsers.py     — BS4-хелперы (grades, people, clean_text)
└── tools/
    ├── auth.py          — ais_whoami, ais_eduroam_credentials
    ├── people.py        — ais_search_people, ais_get_person
    ├── portal.py        — ais_list_studies, ais_portal_menu, ais_contact_departments
    ├── academics.py     — ais_grades, ais_grades_all, ais_plan_progress, ais_course_eplans,
    │                      ais_study_details, ais_schoolmates, ais_excuse_notes, ais_course_syllabus
    ├── lectures.py      — ais_lectures_sheet, ais_course_progress, ais_test_detail
    ├── schedule.py      — ais_schedule, ais_academic_calendar, ais_year_schedule
    ├── exams.py         — ais_list_exams, ais_register_exam, ais_unregister_exam
    ├── courses.py       — ais_course_registration
    ├── thesis.py        — ais_thesis_topics, ais_submissions
    ├── finance.py       — ais_financing, ais_scholarships, ais_orders
    ├── mail.py          — ais_mail_inbox, ais_mail_read, ais_mail_download_attachment,
    │                      ais_mail_reply, ais_mail_forward, ais_mail_folders,
    │                      ais_mail_delete, ais_mail_delete_bulk,
    │                      ais_mail_move, ais_mail_move_bulk,
    │                      ais_mail_mark_read, ais_mail_spam  ⚠️ (write tools included)
    ├── mail_send.py     — ais_mail_send  ⚠️ write (2-step AJAX attachment upload)
    ├── submit_file.py   — ais_list_open_submissions, ais_submit_file  ⚠️ write
    ├── documents.py     — ais_documents, ais_noticeboard
    ├── print_docs.py    — ais_list_print_documents, ais_print_document  ⚠️ write (sealed=True)
    └── generic.py       — ais_fetch_page
```

## Tools (52 штук)

### Read-only
| Tool | Описание |
|------|----------|
| `ais_whoami` | Кто залогинен, текущий studium/obdobi |
| `ais_eduroam_credentials` | Логин/пароль eduroam/wifi |
| `ais_search_people(query, students, staff, suggest)` | Поиск людей в каталоге STU |
| `ais_get_person(id_or_url)` | Профиль человека по ID или URL |
| `ais_list_studies` | Все студии и периоды в аккаунте |
| `ais_portal_menu` | Меню портала студента по категориям |
| `ais_contact_departments(fakulta?)` | Контакты учебного отдела: адрес, часы приёма, контактные лица, проректора |
| `ais_grades` | Курсы и результаты текущего периода |
| `ais_grades_all` | Все оценки за всё время учёбы |
| `ais_plan_progress` | Прогресс по учебному плану |
| `ais_course_eplans` | Программы/силлабусы курсов |
| `ais_study_details` | Детали учёбы: программа, кредиты, степень, дата начала, финансирование, карта ISIC |
| `ais_schoolmates(course_code?, group?)` | Список однокурсников (все/семинар/группа преподавателя), поддерживает пагинацию |
| `ais_excuse_notes(include_history?)` | История пропусков/объяснительных |
| `ais_course_syllabus(predmet_id)` | Силлабус курса: кредиты, часы, пресеквизиты, оценивание, литература, распределение оценок |
| `ais_lectures_sheet` | Посещаемость по всем курсам: статус каждого занятия (present/absent/excused/…) + predmet_id |
| `ais_course_progress(predmet_id)` | Промежуточные оценки и список тестов (с detail_id) по курсу |
| `ais_test_detail(detail_id, predmet_id)` | Разбор теста по вопросам: текст вопроса, ответ, баллы |
| `ais_list_print_documents` | Список доступных документов для скачивания/печати |
| `ais_schedule` | Недельное расписание {Monday: [...], ...} |
| `ais_academic_calendar` | Обзор недель семестра |
| `ais_year_schedule` | Ключевые даты учебного года |
| `ais_list_exams(mode, course_code)` | Экзамены: available / registered / past |
| `ais_course_registration` | Статус регистрации на курсы |
| `ais_thesis_topics` | Темы дипломных работ |
| `ais_submissions` | Список submission box-ов с дедлайнами |
| `ais_list_open_submissions` | Открытые для загрузки submission box-ы с ID |
| `ais_financing` | Финансирование обучения |
| `ais_scholarships` | Выплаченные стипендии |
| `ais_orders` | Финансовые ордера (ISIC, транспорт) |
| `ais_mail_inbox(folder, limit)` | Входящие: отправитель, тема, дата, флаги непрочитанного/вложений |
| `ais_mail_read(message_id, folder_id?)` | Прочитать сообщение: заголовки, тело, список вложений |
| `ais_mail_download_attachment(message_id, pid, folder_id?, save_to?)` | Скачать вложение в ~/Downloads |
| `ais_mail_folders` | Список папок с количеством непрочитанных и folder_id |
| `ais_documents` | Новые документы на сервере |
| `ais_noticeboard` | Объявления |
| `ais_fetch_page(url)` | Fetch любой AIS страницы (escape hatch) |

### Write (реальные действия в АИС ⚠️)
| Tool | Описание |
|------|----------|
| `ais_register_exam(exam_id)` | Записаться на экзамен |
| `ais_unregister_exam(exam_id)` | Отписаться от экзамена |
| `ais_mail_send(to, subject, body, cc?, bcc?, message_type?, attachments?, confirm_receipt?, keep_message?, keep_addresses?, save_sent?)` | Отправить сообщение; attachments — список абс. путей (2-step AJAX upload) |
| `ais_mail_reply(message_id, body, folder_id?, quote_original?, attachments?, save_sent?)` | Ответить на сообщение |
| `ais_mail_forward(message_id, to, folder_id?, body?, include_original?, attachments?, save_sent?)` | Переслать сообщение |
| `ais_mail_delete(message_id, folder_id?)` | Удалить сообщение |
| `ais_mail_delete_bulk(message_ids, folder_id?)` | Удалить несколько сообщений |
| `ais_mail_move(message_id, folder_id, target_folder_id)` | Переместить сообщение в папку |
| `ais_mail_move_bulk(message_ids, folder_id, target_folder_id)` | Переместить несколько сообщений |
| `ais_mail_mark_read(message_ids, folder_id?, unread?)` | Отметить как прочитанное/непрочитанное |
| `ais_mail_spam(message_id, folder_id?)` | Отметить как спам |
| `ais_submit_file(odevzdavarna_id, file_path, description?)` | Загрузить файл в submission box |
| `ais_print_document(doc_type, language?, sealed?, save_to?)` | Скачать PDF (confirmation/registration/enrollment); sealed=True → e-подпись в Document Storage |

Получить `exam_id` → `ais_list_exams(mode="available")`.  
Получить `odevzdavarna_id` → `ais_list_open_submissions`.  
Получить `folder_id` → `ais_mail_folders` (известные: 789370=Inbox, 789371=Sent, 789372=Trash, 789373=Unfinished, 789374=Spam).

## Ключевые URL-ы АИС

```
BASE = https://is.stuba.sk/auth
Логин:       BASE/
Портал:      BASE/student/moje_studium.pl?_m=3110
Оценки:      BASE/student/pruchod_studiem.pl?studium=X;obdobi=Y
Расписание:  BASE/katalog/rozvrhy_view.pl?rozvrh_student_obec=1;rozvrh_student=N
Экзамены:    BASE/student/terminy_seznam.pl?studium=X;obdobi=Y
Почта:       BASE/posta/slozka.pl
Compose:     BASE/posta/nova_zprava.pl
Eduroam:     BASE/wifi/heslo_vpn_sit.pl?_m=3532
Submissions: BASE/student/odevzdavarny.pl?studium=X;obdobi=Y
Силлабус:    BASE/katalog/syllabus.pl?predmet=N
Лекции:      BASE/student/list.pl?studium=X;obdobi=Y
Прогресс:    BASE/student/list.pl?studium=X;obdobi=Y;predmet=N;prubezne=1
Тесты:       BASE/student/list.pl?studium=X;obdobi=Y;predmet=N;test=1
Детали теста: BASE/student/list.pl?studium=X;obdobi=Y;predmet=N;vysledky=1;detail=D
```

## Разработка

- Все парсеры толерантны к ошибкам — возвращают `raw_text` как fallback
- Всегда добавляй `&lang=en` к URL для стабильности парсеров
- `SessionManager` — потокобезопасный синглтон, авто-retry при 403/login-page
- `context.py` кешируется в памяти процесса — сброс через `reset_context()`
- Write-actions всегда идут через CSRF-токены (GET страницы → извлечь hash → POST)
- Вложения в `ais_mail_send`/`ais_mail_reply`/`ais_mail_forward` загружаются в 2 шага: сначала AJAX POST с заголовком `X-Requested-With: XMLHttpRequest` (файл привязывается к hash+serializace), затем основной POST без файла
- Известные folder_id для xsavin: 789370=Inbox, 789371=Sent, 789372=Trash, 789373=Unfinished, 789374=Spam

## Оригинальные скрипты

Исходный код в `/home/dimka/Development/AIS` — 4 скрипта, которые стали основой:
- `stuba-token` → `session.py`
- `stuba-eduroam` → `tools/auth.py`
- `stuba-people-gui` → `tools/people.py`, `parsers.py`
- `stuba-student-gui` → `tools/portal.py`, `tools/generic.py`, `parsers.py`
