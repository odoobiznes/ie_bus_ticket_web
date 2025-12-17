#!/bin/bash

# Скрипт автоматичного розгортання Modern Bus Booking на devops.it-enterprise.cz
# Використання: ./deploy.sh [server_address] [user]

set -e  # Зупинити при першій помилці

# Параметри за замовчуванням
SERVER=${1:-"devops.it-enterprise.cz"}
USER=${2:-"odoo"}
MODULE_NAME="ie_bus_ticket_web"
REMOTE_ADDONS_PATH="/opt/odoo/addons"
LOCAL_MODULE_PATH="."

echo "🚀 Початок розгортання модуля $MODULE_NAME на $SERVER"

# Функція для виведення кольорових повідомлень
print_status() {
    echo -e "\033[1;34m[INFO]\033[0m $1"
}

print_success() {
    echo -e "\033[1;32m[SUCCESS]\033[0m $1"
}

print_error() {
    echo -e "\033[1;31m[ERROR]\033[0m $1"
}

print_warning() {
    echo -e "\033[1;33m[WARNING]\033[0m $1"
}

# Перевірка наявності необхідних файлів
print_status "Перевірка структури модуля..."

required_files=(
    "__manifest__.py"
    "__init__.py"
    "controllers/__init__.py"
    "controllers/main.py"
    "views/templates.xml"
    "static/src/css/modern_booking.css"
)

for file in "${required_files[@]}"; do
    if [[ ! -f "$LOCAL_MODULE_PATH/$file" ]]; then
        print_error "Відсутній обов'язковий файл: $file"
        exit 1
    fi
done

print_success "Структура модуля перевірена"

# Перевірка підключення до сервера
print_status "Перевірка підключення до сервера $SERVER..."

if ! ssh -o ConnectTimeout=10 -o BatchMode=yes "$USER@$SERVER" exit 2>/dev/null; then
    print_error "Не вдається підключитися до сервера $SERVER"
    print_warning "Переконайтеся, що:"
    print_warning "1. SSH ключ налаштований"
    print_warning "2. Сервер доступний"
    print_warning "3. Користувач $USER існує"
    exit 1
fi

print_success "Підключення до сервера встановлено"

# Створення резервної копії (якщо модуль вже існує)
print_status "Створення резервної копії..."

ssh "$USER@$SERVER" "
    if [[ -d '$REMOTE_ADDONS_PATH/$MODULE_NAME' ]]; then
        echo 'Створення резервної копії існуючого модуля...'
        sudo cp -r '$REMOTE_ADDONS_PATH/$MODULE_NAME' '$REMOTE_ADDONS_PATH/${MODULE_NAME}_backup_\$(date +%Y%m%d_%H%M%S)'
        echo 'Резервна копія створена'
    else
        echo 'Модуль не існує, резервна копія не потрібна'
    fi
"

# Завантаження модуля на сервер
print_status "Завантаження модуля на сервер..."

# Використовуємо rsync для ефективного копіювання
rsync -avz --delete \
    --exclude='*.pyc' \
    --exclude='__pycache__' \
    --exclude='.git' \
    --exclude='deploy.sh' \
    "$LOCAL_MODULE_PATH/" "$USER@$SERVER:$REMOTE_ADDONS_PATH/$MODULE_NAME/"

print_success "Модуль завантажено"

# Налаштування прав доступу
print_status "Налаштування прав доступу..."

ssh "$USER@$SERVER" "
    sudo chown -R odoo:odoo '$REMOTE_ADDONS_PATH/$MODULE_NAME'
    sudo chmod -R 755 '$REMOTE_ADDONS_PATH/$MODULE_NAME'
    sudo find '$REMOTE_ADDONS_PATH/$MODULE_NAME' -name '*.py' -exec chmod 644 {} \;
"

print_success "Права доступу налаштовано"

# Перевірка синтаксису Python файлів
print_status "Перевірка синтаксису Python файлів..."

ssh "$USER@$SERVER" "
    cd '$REMOTE_ADDONS_PATH/$MODULE_NAME'
    python3 -m py_compile __init__.py
    python3 -m py_compile controllers/__init__.py
    python3 -m py_compile controllers/main.py
    if [[ -d 'models' ]]; then
        find models -name '*.py' -exec python3 -m py_compile {} \;
    fi
"

print_success "Синтаксис Python файлів перевірено"

# Перезапуск Odoo
print_status "Перезапуск Odoo..."

ssh "$USER@$SERVER" "
    if systemctl is-active --quiet odoo; then
        echo 'Перезапуск systemd сервісу odoo...'
        sudo systemctl restart odoo
        sleep 5
        if systemctl is-active --quiet odoo; then
            echo 'Odoo успішно перезапущено'
        else
            echo 'Помилка при перезапуску Odoo'
            exit 1
        fi
    elif docker ps | grep -q odoo; then
        echo 'Перезапуск Docker контейнера odoo...'
        docker restart \$(docker ps | grep odoo | awk '{print \$1}')
        sleep 10
        if docker ps | grep -q odoo; then
            echo 'Docker контейнер успішно перезапущено'
        else
            echo 'Помилка при перезапуску Docker контейнера'
            exit 1
        fi
    else
        echo 'Не знайдено запущений Odoo сервіс'
        echo 'Будь ласка, перезапустіть Odoo вручну'
    fi
"

print_success "Odoo перезапущено"

# Перевірка доступності модуля
print_status "Перевірка доступності модуля..."

# Чекаємо, поки Odoo повністю запуститься
sleep 10

# Перевіряємо доступність головної сторінки
if curl -s -o /dev/null -w "%{http_code}" "http://$SERVER/bus-booking" | grep -q "200\|302"; then
    print_success "Модуль доступний за адресою: http://$SERVER/bus-booking"
else
    print_warning "Модуль може бути недоступний. Перевірте вручну: http://$SERVER/bus-booking"
fi

# Виведення інструкцій для завершення встановлення
print_success "🎉 Розгортання завершено!"
echo ""
echo "📋 Наступні кроки:"
echo "1. Увійдіть в Odoo як адміністратор: http://$SERVER"
echo "2. Перейдіть: Налаштування → Додатки"
echo "3. Натисніть 'Оновити список додатків'"
echo "4. Знайдіть 'Modern Bus Booking' та встановіть його"
echo "5. Перейдіть на http://$SERVER/bus-booking для перевірки"
echo ""
echo "📚 Документація:"
echo "- README.md - загальна інформація про модуль"
echo "- DEPLOYMENT.md - детальні інструкції з розгортання"
echo ""
echo "🔧 Усунення проблем:"
echo "- Перевірте логи: sudo tail -f /var/log/odoo/odoo.log"
echo "- Перевірте статус сервісу: sudo systemctl status odoo"
echo ""

print_success "Розгортання успішно завершено! 🚀"
