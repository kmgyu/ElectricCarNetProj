document.addEventListener('DOMContentLoaded', () => {
    const API_BASE = '/api'; // API 기본 경로

    // 실시간 데이터 갱신
    const fetchRealTimeData = async () => {
        try {
            const response = await fetch(`${API_BASE}/bigtorage-data`);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const data = await response.json();

            if (data && data.length > 0) {
                const latest = data[0]; // 가장 최신 데이터 사용
                document.getElementById('generation').textContent = `${(latest.power || 0).toFixed(2)} kW`;
                document.getElementById('charging').textContent = `${(latest.charge || 0).toFixed(2)} kW`;
                document.getElementById('discharging').textContent = `${(latest.discharge || 0).toFixed(2)} kW`;
                document.getElementById('load').textContent = `${(latest.load || 0).toFixed(2)} kW`;
            }
        } catch (error) {
            console.error('Error fetching real-time data:', error);
        }
    };


    // 차트 데이터 로딩 및 렌더링
    let chartInstance; // 차트 인스턴스
    // 유틸리티: timestamp 파싱 함수
    const parseCustomDate = (timestamp) => {
        if (!timestamp || typeof timestamp !== 'string' || timestamp.length < 13) {
            console.error('Invalid timestamp:', timestamp);
            return null;
        }
    
        const year = parseInt(timestamp.substring(0, 4), 10);
        const month = parseInt(timestamp.substring(4, 6), 10) - 1; // 월은 0부터 시작
        const day = parseInt(timestamp.substring(6, 8), 10);
        const hour = parseInt(timestamp.substring(9, 11), 10) || 0; // 값이 없으면 0으로 설정
        const minute = parseInt(timestamp.substring(11, 13), 10) || 0;
    
        // Date 객체 생성
        return new Date(year, month, day, hour, minute);
    };

    // 차트 데이터 로딩 및 렌더링
    const fetchForecastChartData = async () => {
        try {
            const response = await fetch(`${API_BASE}/forecast-data`);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const data = await response.json();

            if (data && data.length > 0) {
                // 유효한 데이터만 필터링
                const validData = data.filter((d) => {
                    const parsedDate = parseCustomDate(d.timestamp);
                    return parsedDate !== null && !isNaN(parsedDate);
                });

                // 데이터 정렬 (시간순)
                validData.sort((a, b) => new Date(parseCustomDate(a.timestamp)) - new Date(parseCustomDate(b.timestamp)));

                // 날짜별로 누적 발전량 계산
                const timestamps = [];
                const powerData = [];
                const cumulativeData = [];
                let currentDate = '';
                let dailyCumulative = 0;

                validData.forEach(d => {
                    const date = formatDate(parseCustomDate(d.timestamp), 'date');
                    const time = formatDate(parseCustomDate(d.timestamp), 'time');

                    // 날짜가 변경되면 누적값 초기화
                    if (currentDate !== date) {
                        currentDate = date;
                        dailyCumulative = 0;
                    }

                    // 누적 발전량 계산
                    const powergen = d.powergen || 0;
                    dailyCumulative += powergen;

                    timestamps.push(`${date} ${time}`);
                    powerData.push(powergen);
                    cumulativeData.push(dailyCumulative);
                });

                // 차트 그리기
                const ctx = document.getElementById('dataChart').getContext('2d');
                if (chartInstance) chartInstance.destroy(); // 기존 차트 제거
                chartInstance = new Chart(ctx, {
                    type: 'bar', // 막대 그래프와 선 그래프 혼합
                    data: {
                        labels: timestamps,
                        datasets: [
                            {
                                type: 'line', // 선 그래프
                                label: '예측 발전량',
                                data: powerData,
                                borderColor: '#0077b6',
                                backgroundColor: 'rgba(0, 119, 182, 0.2)',
                                fill: true,
                                yAxisID: 'y1',
                            },
                            {
                                type: 'bar', // 막대 그래프
                                label: '예측 누적 발전량',
                                data: cumulativeData,
                                backgroundColor: 'rgba(255, 99, 132, 0.5)',
                                borderColor: 'rgba(255, 99, 132, 1)',
                                yAxisID: 'y2',
                            },
                        ],
                    },
                    options: {
                        responsive: true,
                        scales: {
                            x: {
                                title: { display: true, text: '시간' },
                                ticks: {
                                    callback: function (value, index, ticks) {
                                        const date = new Date(this.getLabelForValue(value)); // 타임스탬프를 Date 객체로 변환
                                        return formatDate(date, 'time'); // 'HH:MM' 형식으로 반환
                                    },
                                    maxTicksLimit: 10, // 최대 표시 레이블 제한
                                    autoSkip: true, // 레이블 자동 건너뛰기 활성화
                                },
                            },
                            y1: {
                                type: 'linear',
                                position: 'left',
                                title: { display: true, text: '발전량 (kW)' },
                                beginAtZero: true,
                            },
                            y2: {
                                type: 'linear',
                                position: 'right',
                                title: { display: true, text: '누적 발전량 (kW)' },
                                beginAtZero: true,
                                grid: { drawOnChartArea: false }, // 두 번째 축의 그리드 제거
                            },
                        },
                    },
                });
            } else {
                console.warn('No valid data available for the chart.');
            }
        } catch (error) {
            console.error('Error fetching forecast chart data:', error);
        }
    };


    // 유틸리티: 날짜 포맷팅 함수
    const formatDate = (date, type) => {
        if (type === 'time') {
            const hours = date.getHours().toString().padStart(2, '0'); // 두 자리로 시간 표시
            const minutes = date.getMinutes().toString().padStart(2, '0'); // 두 자리로 분 표시
            return `${hours}:${minutes}`; // 'HH:MM' 형식
        }
        if (type === 'date') {
            return date.toLocaleDateString('ko-KR', { year: 'numeric', month: '2-digit', day: '2-digit' });
        }
        return '';
    };
    // 예측 데이터 로딩
    const fetchForecastData = async () => {
        try {
            const response = await fetch(`${API_BASE}/forecast-data`);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const data = await response.json();

            if (data && data.length > 0) {
                // 오늘 날짜 (YYYYMMDD 형식)
                const today = new Date().toISOString().split('T')[0].replace(/-/g, '');
                
                // 오늘 데이터만 필터링
                const todayData = data.filter(d => d.timestamp.startsWith(today));

                // 발전량 합산
                const predictedGeneration = todayData.reduce((sum, d) => sum + (d.powergen || 0), 0);
                document.getElementById('forecast-data').textContent = `${predictedGeneration.toFixed(2)} kW`;
            } else {
                document.getElementById('forecast-data').textContent = '예측 데이터가 없습니다.';
            }
        } catch (error) {
            console.error('Error fetching forecast data:', error);
            document.getElementById('forecast-data').textContent = '예측 데이터를 불러오지 못했습니다.';
        }
    };


    // 초기 데이터 로드
    fetchRealTimeData();
    fetchForecastChartData();
    fetchForecastData();

    // 실시간 데이터 10초마다 갱신
    setInterval(fetchRealTimeData, 10000);
});
