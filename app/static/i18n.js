/* Interface translation.

   The key is the English source string rather than an invented identifier.
   Markup stays readable, and a new string with no translation yet simply
   stays English instead of turning into "admin.backup.hint.2" in plain view.

   The whole tree is translated: text nodes, titles and placeholders.
   Originals are remembered, so switching back needs no reload.

   Action labels and server replies are not here — they arrive already
   translated, because they live in app/i18n.py.

   Lookups collapse whitespace: long hints in the markup are broken across
   lines, and an exact match would never find them. */

(function () {
  const KEY = 'pcr_lang';
  const NAMES = { en: 'English', ru: 'Русский' };

  const RU = {
    ', status without a password —': ', состояние без пароля —',
    '. Action list —': '. Список действий —',
    '. Full description in the project README.': '. Полное описание в README проекта.',
    'A URL is required': 'Нужен адрес',
    'A restart is required.': 'Нужен перезапуск.',
    'A token is a password for machines. Connect integrations with one instead of your own password, and changing that password will not break them all at once. Works anywhere a password is accepted, plus as a header':
      'Токен — это пароль для машины. Интеграции лучше подключать им, а не вашим паролем: тогда смена пароля не сломает их все разом. Работает везде, где принимается пароль, плюс заголовком',
    'Access': 'Доступ',
    'Access password required.': 'Нужен пароль доступа.',
    'Actions': 'Действия',
    'Actions enabled': 'Действий включено',
    'Address': 'Адрес',
    'Allowed networks': 'Разрешённые сети',
    'Anything using "%s" stops working immediately.':
      'Всё, что пользуется токеном «%s», сразу перестанет работать.',
    'Applied after a restart. Bookmarks, the smart home and any integration have to follow it.':
      'Применяется после перезапуска. Закладки, умный дом и любые интеграции должны последовать за ним.',
    'At least 4 characters': 'Минимум 4 символа',
    'At least one delay option is required': 'Нужен хотя бы один вариант задержки',
    'Autostart': 'Автозапуск',
    'Autostart disabled. The running process keeps working.':
      'Автозапуск выключен. Текущий процесс продолжает работать.',
    'Autostart enabled': 'Автозапуск включён',
    'Back to remote': 'К пульту',
    'Backup downloaded': 'Копия скачана',
    'Backups': 'Резервные копии',
    'Bridge is up, check the status': 'Мост поднят, проверьте состояние',
    'Broker address': 'Адрес брокера',
    'CANCEL': 'ОТМЕНИТЬ',
    'Cancel': 'Отменить',
    'Change password': 'Сменить пароль',
    'Changing the password signs out every device that remembered it and breaks integrations using it. To avoid that, move them to tokens on the Integrations tab.':
      'Смена пароля разлогинит все устройства, где он сохранён, и сломает интеграции, которые ходят с ним же. Чтобы этого не случалось, переведите их на токены во вкладке «Интеграции».',
    'Checking the connection…': 'Проверяю связь…',
    'Checking…': 'Проверяю…',
    'Choose a backup file': 'Выберите файл резервной копии',
    'Computer': 'Компьютер',
    'Computer name in the interface': 'Имя компьютера в интерфейсе',
    'Copied': 'Скопировано',
    'Copy': 'Скопировать',
    'Copy the token now': 'Скопируйте токен сейчас',
    'Could not read the file': 'Не разобрал файл',
    'Create': 'Создать',
    'Current settings will be replaced by the ones in "%s".':
      'Текущие настройки будут заменены теми, что в «%s».',
    'Custom launch buttons': 'Свои кнопки запуска',
    'Default delay, seconds': 'Задержка по умолчанию, секунд',
    'Delay before shutdown': 'Задержка перед выключением',
    'Delay options on the remote': 'Варианты задержки на пульте',
    'Describe what the token is for': 'Напишите, для чего токен',
    'Device name in the smart home': 'Имя устройства в умном доме',
    'Done': 'Готово',
    'Download a backup': 'Скачать копию',
    'Enter the access password — it will be remembered on this device.':
      'Введите пароль доступа — он запомнится на этом устройстве.',
    'Enter the password': 'Введите пароль',
    'Error': 'Ошибка',
    'Failed attempts before lockout': 'Промахов пароля до блокировки',
    'Fill in the name and the target': 'Заполните название и цель',
    'For example': 'Например',
    'How often, hours': 'Как часто, часов',
    'How your smart home and scripts talk to the remote.':
      'Как с пультом разговаривают система умного дома и скрипты.',
    'Include password and tokens': 'Включить пароль и токены',
    'Integrations': 'Интеграции',
    'Issue': 'Выпустить',
    'It is shown once and cannot be retrieved later.':
      'Он показывается один раз, потом получить его будет негде.',
    'Language': 'Язык',
    'Lockout, seconds': 'Блокировка, секунд',
    'Log': 'Журнал',
    'MQTT bridge': 'Мост MQTT',
    'MQTT with auto-discovery': 'MQTT с автообнаружением',
    'Name': 'Название',
    'Needed after changing the port, restoring a backup, or toggling the tray icon.':
      'Нужен после смены порта, восстановления из копии и включения или выключения значка в трее.',
    'Needed when moving to another machine': 'Нужно для переезда на другую машину',
    'New password': 'Новый пароль',
    'No connection to the computer': 'Нет связи с компьютером',
    'No targets are enabled': 'Нет включённых адресов',
    'No targets yet.': 'Адресов пока нет.',
    'No tokens yet.': 'Токенов пока нет.',
    'Nothing yet.': 'Пока пусто.',
    'OK': 'ОК',
    'One per line. Anything outside the list is refused — even if the port gets exposed by accident.':
      'По одной на строку. Всё, что не попало в список, получает отказ — даже если порт случайно пробросят наружу.',
    'Overview': 'Обзор',
    'Password': 'Пароль',
    'Pick a password': 'Придумайте пароль',
    'Port': 'Порт',
    'Re-register': 'Перерегистрировать',
    'Reconnect': 'Подключиться заново',
    'Refresh': 'Обновить',
    'Remote': 'Пульт',
    'Remote ·': 'Пульт ·',
    'Repeat the password': 'Повторите пароль',
    'Restart': 'Перезапуск',
    'Restart now': 'Перезапустить',
    'Restart the remote': 'Перезапустить пульт',
    'Restart without saving?': 'Перезапустить без сохранения?',
    'Restarting in': 'Перезагрузка через',
    'Restarting, back in a couple of seconds': 'Перезапускаюсь, вернусь через пару секунд',
    'Restore': 'Восстановить',
    'Restore from a file': 'Восстановить из файла',
    'Restore from this file?': 'Восстановить из этого файла?',
    'Restoring applies the settings and requires a restart. If the backup had no secrets, the current password stays as it is.':
      'Восстановление применяет настройки и требует перезапуска. Если в копии не было секретов, действующий пароль останется прежним.',
    'Revoke': 'Отозвать',
    'Revoke this token?': 'Отозвать этот токен?',
    'Right-click menu with actions. Requires a restart.':
      'Меню действий по правому клику. Нужен перезапуск.',
    'Save changes': 'Сохранить изменения',
    'Save your changes first': 'Сначала сохраните изменения',
    'Saved': 'Сохранено',
    'Saved. A restart is required.': 'Сохранено. Нужен перезапуск.',
    'Select it and copy by hand': 'Выделите и скопируйте вручную',
    'Send now': 'Отправить сейчас',
    'Send on a schedule': 'Отправлять по расписанию',
    'Sending to external targets': 'Отправка на внешние адреса',
    'Sending…': 'Отправка…',
    'Service status': 'Состояние служб',
    'Settings': 'Настройки',
    'Settings pile up over months and vanish in a single reinstall.':
      'Настройки накапливаются месяцами и теряются в одну переустановку.',
    'Settings restored.': 'Настройки восстановлены.',
    'Settings ·': 'Настройки ·',
    'Shutdown, restart and cancel cannot be disabled: external integrations usually depend on them, and their disappearance breaks automations silently.':
      'Выключение, перезагрузка и отмена отключить нельзя: на них обычно завязаны внешние интеграции, и их пропажа ломает сценарии молча.',
    'Shutting down in': 'Выключение через',
    'Sign in': 'Войти',
    'Start at sign-in': 'Запускать при входе в систему',
    'Startup': 'Запуск',
    'Sure?': 'Точно?',
    'System': 'Система',
    'The access password is required.': 'Нужен пароль доступа.',
    'The autostart task points elsewhere: the project probably moved or the interpreter changed. The remote will not come back after a reboot.':
      'Задача автозапуска ведёт не туда: похоже, проект переехал или сменился интерпретатор. После перезагрузки пульт не поднимется.',
    'The backup is sent as a POST with a JSON body. Any receiver will do: object storage behind your own gateway, a NAS, a hypervisor, an automation webhook.':
      'Копия уходит методом POST с телом JSON. Подойдёт любой приёмник: объектное хранилище через свой шлюз, NAS, гипервизор, вебхук автоматизации.',
    'The computer is not responding.': 'Компьютер не отвечает.',
    'The network list cannot be empty': 'Список сетей не может быть пустым',
    'The only place that shows what the remote did and where it failed.':
      'Единственное место, где видно, что пульт делал и на чём падал.',
    'The password did not work': 'Пароль не подошёл',
    'The password is set by the environment variable': 'Пароль задан переменной окружения',
    'The two passwords do not match': 'Пароли не совпадают',
    'Theme': 'Тема',
    'There are unsaved changes and they will be lost.':
      'Есть несохранённые изменения, они будут потеряны.',
    'Token issued': 'Токен выпущен',
    'Token not found': 'Токен не найден',
    'Token revoked': 'Токен отозван',
    'Tokens': 'Токены',
    'Tray icon': 'Значок в трее',
    'Until there is one the remote is not protected at all. Whoever sets it first is the one who can shut this computer down.':
      'Пока его нет, пульт не защищён вообще ничем. Кто задаст пароль первым, тот и сможет выключать этот компьютер.',
    'Uptime': 'Время работы',
    'Used whenever the delay is not given explicitly, including calls from outside. Change with care.':
      'Применяется, когда задержку не указали явно — в том числе при вызове снаружи. Менять осторожно.',
    'Username': 'Логин',
    'Version': 'Версия',
    'What is going on with the remote.': 'Что сейчас происходит с пультом.',
    'What is it for': 'Для чего выпускаем',
    'What the remote is called, when it starts and how to restart it.':
      'Как пульт называется, когда запускается и как перезапустить.',
    'What the remote shows and what the API exposes.':
      'Что показывать на пульте и отдавать наружу по API.',
    'Who is allowed in, and what happens to password guessers.':
      'Кого пускать и что делать с теми, кто подбирает пароль.',
    'Wrong password': 'Неверный пароль',
    'Your smart home will create a device with every button and sensor by itself — no manual definitions needed. State is pushed the moment it changes, and if the computer dies suddenly, the broker announces it offline for us.':
      'Умный дом сам создаст устройство со всеми кнопками и сенсорами — описывать их вручную не нужно. Состояние уходит сразу при изменении, а если компьютер внезапно умрёт, брокер объявит его офлайн за нас.',
    'broker password': 'пароль брокера',
    'check that the computer is on and online': 'проверьте, что компьютер включён и в сети',
    'checking…': 'проверяю…',
    'connected': 'подключён',
    'connecting…': 'соединяюсь…',
    'created': 'создан',
    'dark': 'тёмная',
    'disabled': 'отключена',
    'follow system': 'как в системе',
    'last': 'последняя',
    'last reply': 'последний ответ',
    'last used': 'использован',
    'leave empty to keep the current one': 'оставьте пустым, чтобы не менять',
    'light': 'светлая',
    'loading…': 'загружаю…',
    'manual only': 'только вручную',
    'never sent yet': 'ещё ни разу не отправлялась',
    'never used': 'ещё не использовался',
    'no connection': 'нет связи',
    'no connection to the broker': 'нет связи с брокером',
    'now': 'сразу',
    'of': 'из',
    'off': 'выключен',
    'off — the remote will not come back after a reboot':
      'выключен — после перезагрузки пульт не поднимется',
    'on': 'включён',
    'on a schedule': 'по расписанию',
    'online': 'в сети',
    'or a full path to a program. This runs arbitrary code: enable it deliberately and only with a strong password.':
      'или полный путь до программы. Это запуск произвольного кода: включайте осознанно и только со стойким паролем.',
    'or drag one here': 'или перетащите его сюда',
    'path or URI': 'путь или URI',
    'registered': 'зарегистрирована',
    's': 'с',
    'set — leave empty to keep it': 'задан — оставьте пустым, чтобы не менять',
    'shown': 'показан',
    'target(s)': 'адрес(а)',
    'task': 'задача',
    'the log is empty': 'журнал пуст',
    'the task points elsewhere': 'задача ведёт не туда',
    'topics': 'топики',
    'uptime': 'аптайм',
    'used by integrations — cannot be disabled': 'используется интеграциями — не отключается',
    'with body': 'с телом',
    '— it takes precedence over the file, so changing it here has no effect.':
      '— она важнее файла, и смена здесь ни на что не повлияет.',
  };

  function detect() {
    // Follow the browser unless the visitor picked something
    const nav = (navigator.language || 'en').toLowerCase();
    return nav.startsWith('ru') ? 'ru' : 'en';
  }

  function read() {
    try { return localStorage.getItem(KEY) || detect(); } catch { return detect(); }
  }

  const FLAT = {};
  Object.keys(RU).forEach((k) => { FLAT[k.replace(/\s+/g, ' ').trim()] = RU[k]; });

  /** Fill %s placeholders left to right. */
  function fill(text, args) {
    let i = 0;
    return text.replace(/%s/g, () => (i < args.length ? String(args[i++]) : '%s'));
  }

  /* Translate one string. Not in the dictionary means returned unchanged.

     Values belong in args rather than in the text: interpolating a name into
     the string first would make every call its own key, and a key with a name
     baked into it can never be in the dictionary. */
  function s(text, ...args) {
    const raw = String(text);
    const done = (v) => (args.length ? fill(v, args) : v);
    if (read() === 'en') return done(raw);
    const flat = raw.replace(/\s+/g, ' ').trim();
    if (!flat) return raw;
    const hit = FLAT[flat];
    if (!hit) return done(raw);
    // Keep leading and trailing whitespace: the layout leans on it
    const lead = raw.match(/^\s*/)[0];
    const tail = raw.match(/\s*$/)[0];
    return done(lead + hit + tail);
  }

  const ORIGIN = new WeakMap();

  function remember(node, prop, value) {
    let box = ORIGIN.get(node);
    if (!box) ORIGIN.set(node, (box = {}));
    if (!(prop in box)) box[prop] = value;
    return box[prop];
  }

  function apply(root) {
    root = root || document.body;
    if (!root) return;
    const translate = read() === 'ru';

    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const texts = [];
    while (walker.nextNode()) texts.push(walker.currentNode);
    texts.forEach((node) => {
      if (!node.nodeValue.trim()) return;
      const src = remember(node, 'text', node.nodeValue);
      node.nodeValue = translate ? s(src) : src;
    });

    root.querySelectorAll('[placeholder]').forEach((el) => {
      const src = remember(el, 'ph', el.placeholder);
      el.placeholder = translate ? s(src) : src;
    });
    root.querySelectorAll('[title]').forEach((el) => {
      const src = remember(el, 'title', el.title);
      el.title = translate ? s(src) : src;
    });
    document.documentElement.lang = read();
  }

  window.I18n = {
    get lang() { return read(); },
    get name() { return NAMES[read()]; },
    s,
    apply,
    set(lang) {
      try { localStorage.setItem(KEY, lang); } catch {}
      apply();
      window.dispatchEvent(new CustomEvent('langchange', { detail: lang }));
    },
    next() {
      const lang = read() === 'en' ? 'ru' : 'en';
      this.set(lang);
      return lang;
    },
    /** Toggle button: draws its own icon and label. */
    bindButton(el, decorate) {
      const paint = () => {
        el.innerHTML = `<svg><use href="#i-language"></use></svg>`;
        el.title = `Language: ${NAMES[read()]}`;
        el.setAttribute('aria-label', el.title);
        if (decorate) decorate(read(), NAMES[read()]);
      };
      el.onclick = () => { this.next(); paint(); };
      paint();
    },
  };

  document.addEventListener('DOMContentLoaded', () => apply());
})();
