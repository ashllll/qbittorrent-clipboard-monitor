// qBittorrent 监控仪表板 JavaScript

class DashboardApp {
    constructor() {
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 5000; // 5秒

        // 图表实例
        this.cpuChart = null;
        this.memoryChart = null;

        // 数据缓存
        this.performanceData = [];
        this.maxDataPoints = 60; // 显示最近60个数据点

        this.init();
    }

    init() {
        this.initCharts();
        this.connectWebSocket();
        this.loadInitialData();
        this.setupEventListeners();
    }

    initCharts() {
        const chartOptions = {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    ticks: {
                        callback: function(value) {
                            return value + '%';
                        }
                    }
                },
                x: {
                    type: 'time',
                    time: {
                        displayFormats: {
                            minute: 'HH:mm',
                            hour: 'HH:mm'
                        }
                    }
                }
            },
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    callbacks: {
                        label: function(context) {
                            return `${context.dataset.label}: ${context.parsed.y.toFixed(1)}%`;
                        }
                    }
                }
            },
            elements: {
                line: {
                    tension: 0.4
                },
                point: {
                    radius: 2,
                    hoverRadius: 5
                }
            }
        };

        // CPU图表
        const cpuCtx = document.getElementById('cpu-chart').getContext('2d');
        this.cpuChart = new Chart(cpuCtx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'CPU使用率',
                    data: [],
                    borderColor: 'rgb(255, 99, 132)',
                    backgroundColor: 'rgba(255, 99, 132, 0.1)',
                    fill: true
                }]
            },
            options: chartOptions
        });

        // 内存图表
        const memoryCtx = document.getElementById('memory-chart').getContext('2d');
        this.memoryChart = new Chart(memoryCtx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: '内存使用率',
                    data: [],
                    borderColor: 'rgb(54, 162, 235)',
                    backgroundColor: 'rgba(54, 162, 235, 0.1)',
                    fill: true
                }]
            },
            options: chartOptions
        });
    }

    connectWebSocket() {
        try {
            this.ws = new WebSocket(`ws://${window.location.host}/ws`);
            this.setupWebSocketHandlers();
        } catch (error) {
            console.error('WebSocket连接失败:', error);
            this.updateConnectionStatus(false);
        }
    }

    setupWebSocketHandlers() {
        this.ws.onopen = () => {
            console.log('WebSocket连接已建立');
            this.reconnectAttempts = 0;
            this.updateConnectionStatus(true);
        };

        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleWebSocketMessage(data);
            } catch (error) {
                console.error('解析WebSocket消息失败:', error);
            }
        };

        this.ws.onclose = () => {
            console.log('WebSocket连接已关闭');
            this.updateConnectionStatus(false);
            this.attemptReconnect();
        };

        this.ws.onerror = (error) => {
            console.error('WebSocket错误:', error);
            this.updateConnectionStatus(false);
        };
    }

    handleWebSocketMessage(data) {
        switch (data.type) {
            case 'performance_update':
                this.updatePerformanceData(data.data);
                break;
            case 'alert':
                this.addAlert(data.data);
                break;
            default:
                console.log('未知消息类型:', data.type);
        }
    }

    updatePerformanceData(data) {
        // 更新关键指标卡片
        this.updateMetricCards(data);

        // 更新图表数据
        this.updateCharts(data);

        // 缓存数据
        this.performanceData.push({
            timestamp: new Date(),
            ...data
        });

        // 限制数据点数量
        if (this.performanceData.length > this.maxDataPoints) {
            this.performanceData.shift();
        }

        // 更新最后更新时间
        this.updateLastUpdateTime();
    }

    updateMetricCards(data) {
        // CPU使用率
        const cpuValue = data.cpu_percent || 0;
        document.getElementById('cpu-value').textContent = `${cpuValue.toFixed(1)}%`;
        this.updateMetricClass('cpu-value', cpuValue);

        // 内存使用率
        const memoryValue = data.memory_percent || 0;
        document.getElementById('memory-value').textContent = `${memoryValue.toFixed(1)}%`;
        this.updateMetricClass('memory-value', memoryValue);

        // 进程数
        const processCount = data.process_count || 0;
        document.getElementById('processes-value').textContent = processCount;

        // 连接数（如果有）
        if (data.active_connections !== undefined) {
            document.getElementById('connections-value').textContent = data.active_connections;
        }
    }

    updateMetricClass(elementId, value) {
        const element = document.getElementById(elementId);
        element.className = element.className.replace(/\bmetric-\w+\b/g, '');

        if (value >= 90) {
            element.classList.add('metric-high');
        } else if (value >= 75) {
            element.classList.add('metric-warning');
        } else {
            element.classList.add('metric-normal');
        }
    }

    updateCharts(data) {
        const timestamp = new Date();

        // 更新CPU图表
        this.updateChart(this.cpuChart, timestamp, data.cpu_percent || 0);

        // 更新内存图表
        this.updateChart(this.memoryChart, timestamp, data.memory_percent || 0);
    }

    updateChart(chart, timestamp, value) {
        chart.data.labels.push(timestamp);
        chart.data.datasets[0].data.push(value);

        // 限制数据点数量
        const maxPoints = this.maxDataPoints;
        if (chart.data.labels.length > maxPoints) {
            chart.data.labels.shift();
            chart.data.datasets[0].data.shift();
        }

        chart.update('none'); // 无动画更新以提高性能
    }

    addAlert(alert) {
        const alertsList = document.getElementById('alerts-list');
        const existingNoAlerts = alertsList.querySelector('.text-center.text-muted');

        // 移除"无告警"消息（如果存在）
        if (existingNoAlerts) {
            existingNoAlerts.remove();
        }

        // 创建告警元素
        const alertElement = document.createElement('div');
        alertElement.className = `alert-item alert-${alert.level}`;
        alertElement.innerHTML = `
            <div class="d-flex justify-content-between align-items-start">
                <div>
                    <strong>${this.getAlertIcon(alert.level)} ${alert.message}</strong>
                </div>
                <small class="alert-time">${new Date(alert.timestamp).toLocaleTimeString()}</small>
            </div>
        `;

        // 添加到列表顶部
        alertsList.insertBefore(alertElement, alertsList.firstChild);

        // 限制告警数量
        const maxAlerts = 10;
        const alertItems = alertsList.querySelectorAll('.alert-item');
        if (alertItems.length > maxAlerts) {
            for (let i = maxAlerts; i < alertItems.length; i++) {
                alertItems[i].remove();
            }
        }

        // 添加动画效果
        alertElement.classList.add('slide-in');
    }

    getAlertIcon(level) {
        switch (level) {
            case 'critical':
                return '<i class="fas fa-exclamation-circle text-danger"></i>';
            case 'warning':
                return '<i class="fas fa-exclamation-triangle text-warning"></i>';
            default:
                return '<i class="fas fa-info-circle text-info"></i>';
        }
    }

    updateConnectionStatus(connected) {
        const statusElement = document.getElementById('status');
        if (connected) {
            statusElement.innerHTML = '<i class="fas fa-circle text-success"></i> 已连接';
        } else {
            statusElement.innerHTML = '<i class="fas fa-circle text-danger"></i> 连接断开';
        }
    }

    updateLastUpdateTime() {
        const lastUpdateElement = document.getElementById('last-update');
        lastUpdateElement.textContent = new Date().toLocaleString();
    }

    attemptReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            console.log(`尝试重新连接... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);

            setTimeout(() => {
                this.connectWebSocket();
            }, this.reconnectDelay);
        } else {
            console.error('达到最大重连次数，停止重连');
            this.updateConnectionStatus(false);
        }
    }

    async loadInitialData() {
        try {
            // 加载当前统计
            const statsResponse = await fetch('/api/stats');
            const statsData = await statsResponse.json();

            if (statsData.status === 'success') {
                this.updatePerformanceData(statsData.data);
            }

            // 加载系统信息
            const systemResponse = await fetch('/api/system');
            const systemData = await systemResponse.json();

            if (systemData.status === 'success') {
                this.updateSystemInfo(systemData.data);
            }

            // 加载历史数据
            const historyResponse = await fetch('/api/history?minutes=60');
            const historyData = await historyResponse.json();

            if (historyData.status === 'success') {
                this.loadHistoricalData(historyData.data);
            }

            // 加载告警
            const alertsResponse = await fetch('/api/alerts');
            const alertsData = await alertsResponse.json();

            if (alertsData.status === 'success') {
                this.loadAlerts(alertsData.data);
            }

        } catch (error) {
            console.error('加载初始数据失败:', error);
        }
    }

    loadHistoricalData(data) {
        // 按时间排序
        data.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));

        data.forEach(point => {
            const timestamp = new Date(point.timestamp);

            // 更新CPU图表
            if (point.cpu_percent !== undefined) {
                this.updateChart(this.cpuChart, timestamp, point.cpu_percent);
            }

            // 更新内存图表
            if (point.memory_percent !== undefined) {
                this.updateChart(this.memoryChart, timestamp, point.memory_percent);
            }
        });
    }

    loadAlerts(alerts) {
        const alertsList = document.getElementById('alerts-list');

        if (alerts.length === 0) {
            alertsList.innerHTML = `
                <div class="text-center text-muted">
                    <i class="fas fa-check-circle fa-3x"></i>
                    <p class="mt-2">暂无告警</p>
                </div>
            `;
            return;
        }

        alertsList.innerHTML = '';
        alerts.forEach(alert => {
            this.addAlert(alert);
        });
    }

    updateSystemInfo(systemInfo) {
        document.getElementById('platform').textContent = systemInfo.platform || '--';
        document.getElementById('python-version').textContent = systemInfo.python_version || '--';
        document.getElementById('cpu-count').textContent = systemInfo.cpu_count || '--';
        document.getElementById('memory-total').textContent = this.formatBytes(systemInfo.memory_total || 0);
    }

    formatBytes(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    setupEventListeners() {
        // 窗口大小改变时重新渲染图表
        window.addEventListener('resize', () => {
            if (this.cpuChart) this.cpuChart.resize();
            if (this.memoryChart) this.memoryChart.resize();
        });

        // 页面可见性改变时的处理
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                console.log('页面隐藏，暂停数据更新');
            } else {
                console.log('页面显示，恢复数据更新');
            }
        });

        // 定期刷新连接状态
        setInterval(() => {
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.updateConnectionStatus(true);
            }
        }, 30000); // 每30秒检查一次
    }
}

// 页面加载完成后初始化应用
document.addEventListener('DOMContentLoaded', () => {
    window.dashboardApp = new DashboardApp();
});

// 处理页面卸载
window.addEventListener('beforeunload', () => {
    if (window.dashboardApp && window.dashboardApp.ws) {
        window.dashboardApp.ws.close();
    }
});