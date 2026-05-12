# ObsidianAI Usage Guide

## 1. Запуск на Mac

Открой терминал:

```bash
cd "/Users/justalim/projects/новый проект"
./scripts/start_dev.sh
```

Скрипт поднимает:

- backend: `http://localhost:8765`
- web UI: `http://localhost:5173`
- phone UI: `http://<mac-ip>:5173`

Если нужен автозапуск после входа в macOS:

```bash
cd "/Users/justalim/projects/новый проект"
./scripts/install_launch_agents.sh
```

## 2. Проверка Qwen3

Модель устанавливается через Ollama:

```bash
ollama pull qwen3
ollama run qwen3
```

В веб-интерфейсе открой `Settings` и проверь `Default local model`: должно быть `qwen3:latest`.

## 3. Подключение с телефона

1. Mac и телефон должны быть в одной Wi-Fi сети.
2. На Mac открой `http://localhost:5173`.
3. В `Settings` посмотри `LAN token fingerprint`.
4. Сам токен лежит локально:

```text
/Users/justalim/projects/новый проект/data/auth-token.txt
```

5. На телефоне открой URL из `Dashboard`/`Settings`, обычно:

```text
http://192.168.0.219:5173
```

6. Когда появится экран `Secure LAN Access`, вставь токен один раз и нажми `Save token`.

Важная деталь: телефон теперь обращается к API через тот же порт `5173` (`/api` proxy). Это снижает шанс ошибки “нет связи с backend”, потому что браузеру телефона не нужно отдельно пробиваться на порт `8765`.

## 4. Выбор рабочей директории

Перед задачей для ИИ открой `Command`:

1. В блоке `Active Workspace` выбери проект.
2. Нажми `Save workspace`.
3. После этого режим `Actions` будет создавать `write_file` только внутри выбранной папки.

Если нужно работать в другом проекте, сначала переключи workspace. Backend дополнительно проверяет путь и не даст записать файл вне выбранной директории.

## 5. Как пользоваться ИИ

В `Command` есть два режима:

- `Chat` — поговорить с ИИ по vault и проектам.
- `Actions` — попросить ИИ подготовить изменения.
- `Plan` — попросить ИИ сначала создать пошаговый execution plan.

Режим `Actions` не применяет изменения сразу. Он создает pending actions с diff. Потом:

1. Открой `Approval Queue`.
2. Проверь diff.
3. Нажми `Approve` или `Reject`.

## 5.1. Execution Plans

Открой `Plans` или выбери `Plan` в `Command`.

1. Выбери workspace.
2. Опиши большую задачу.
3. Нажми `Create plan`.
4. Проверь шаги, риски, файлы и проверки.
5. Нажми `Approve plan` или отклони план.
6. Отдельные шаги можно помечать как approved/completed/rejected.

План не меняет файлы сам. Он создает управляемую структуру работы, после которой изменения
идут через обычную очередь approval actions.

## 5.2. Learning

Открой `Learning`.

- `Add Memory` — вручную добавляет правило, паттерн или предпочтение.
- `Teach Assistant` — превращает твою поправку в learning memory.
- В режиме `review` память сначала попадает в очередь проверки.
- Только `active` memory попадает в chat и planning context.

Это способ обучать ассистента под себя без скрытой самодеятельности.

## 5.3. Project Health and Checks

В `Command` карточка `Context Pack` показывает health score и найденные проверки.
В `Plans` можно запускать safe checks, например `npm run build`.
Backend разрешает только проверочные команды из allowlist.

## 6. Работа через Obsidian Mobile

Мобильный bridge можно запустить отдельно:

```bash
cd "/Users/justalim/projects/новый проект"
source .venv/bin/activate
python3 scripts/obsidian_local_agent.py
```

С телефона в Obsidian добавь задачу в:

```text
inbox/remote-tasks.md
```

Формат:

```markdown
- [ ] Проверь проект SmartKit и подготовь план исправлений
```

Bridge прочитает задачу, обратится к Qwen3 и создаст pending actions, если нужны изменения файлов.

## 7. Быстрая диагностика

Backend:

```bash
curl http://127.0.0.1:8765/api/health
```

Web proxy:

```bash
curl http://127.0.0.1:5173/api/health
```

Телефонный URL с Mac:

```bash
ipconfig getifaddr en0
```

Порты:

```bash
lsof -nP -iTCP:8765 -sTCP:LISTEN
lsof -nP -iTCP:5173 -sTCP:LISTEN
```

Логи автозапуска:

```text
/Users/justalim/projects/новый проект/data/logs/
```
