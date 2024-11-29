const socket = io();
let timerInterval;
let currentUser = null;
const QUEUE_TIMEOUT = 30;
let myUserId = null;
let selectedEventId = null;

document.querySelectorAll('.reserve-btn').forEach(button => {
    button.addEventListener('click', () => {
        selectedEventId = button.closest('.event-card').getAttribute('data-id');
        openModal();
    });
});

socket.on('update_events', (events) => {
    const eventsContainer = document.getElementById('events');
    eventsContainer.innerHTML = ''; // Limpa o container
    
    events.forEach(event => {
        const card = document.createElement('div');
        card.className = 'event-card';
        card.setAttribute('data-id', event.id);
        card.innerHTML = `
            <div class="event-header">
                <h3>${event.name}</h3>
                <span class="slots-badge">${event.slots} vagas</span>
            </div>
            <div class="event-content">
                <button class="reserve-btn">Reservar Vaga</button>
            </div>
        `;
        eventsContainer.appendChild(card);
    });

    // Reattach event listeners
    document.querySelectorAll('.reserve-btn').forEach(button => {
        button.addEventListener('click', () => {
            selectedEventId = button.closest('.event-card').getAttribute('data-id');
            openModal();
        });
    });
});

socket.on('error', (data) => {
    alert(data.message);
});

socket.on('update_queue', (data) => {
    const queueList = document.getElementById('queue-list');
    queueList.innerHTML = '';
    data.queue.forEach(user => {
        const listItem = document.createElement('li');
        if (user === myUserId) {
            listItem.innerHTML = `${user} <span class="current-user-badge">EU</span>`;
            listItem.classList.add('my-user');
        } else {
            listItem.textContent = user;
        }
        queueList.appendChild(listItem);
    });
});

socket.on('current_state', (data) => {
    document.getElementById('current-user-id').textContent = data.current_user;
    resetAndStartTimer(data.time_left);
});

function resetAndStartTimer(initialTime = 30) {
    if (timerInterval) {
        clearInterval(timerInterval);
        timerInterval = null;
    }
    
    const timeLeftElement = document.getElementById('time-left');
    let timeLeft = initialTime;
    timeLeftElement.textContent = timeLeft;

    timerInterval = setInterval(() => {
        timeLeft -= 1;
        timeLeftElement.textContent = timeLeft;
        
        if (timeLeft <= 0) {
            clearInterval(timerInterval);
            timerInterval = null;
            
            setTimeout(() => {
                socket.emit('time_expired');
                socket.emit('request_state');
            }, 0);
        }
    }, 1000);
}

socket.on('update_events', () => {
    if (!timerInterval && document.getElementById('time-left').textContent === '0') {
        socket.emit('time_expired');
        socket.emit('request_state');
    }
});

socket.on('reset_timer', () => {
    resetAndStartTimer(QUEUE_TIMEOUT);
});

// Solicitar estado atual ao conectar
socket.on('connect', () => {
    socket.emit('request_state');
});

// Adicionar listener para atualização de usuários online
socket.on('update_online_users', (data) => {
    document.getElementById('online-count').textContent = data.count;
});

socket.on('your_user_id', (data) => {
    myUserId = data.user_id;
});

function openModal() {
    document.getElementById('confirmationModal').style.display = 'flex';
}

function closeModal() {
    document.getElementById('confirmationModal').style.display = 'none';
    document.getElementById('userName').value = '';
    document.getElementById('userPhone').value = '';
}

function confirmReservation() {
    const name = document.getElementById('userName').value;
    const phone = document.getElementById('userPhone').value;
    
    if (!name || !phone) {
        alert('Por favor, preencha todos os campos');
        return;
    }

    socket.emit('reserve_slot', {
        event_id: parseInt(selectedEventId),
        user_name: name,
        user_phone: phone
    });
    
    closeModal();
}
