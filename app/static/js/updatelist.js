function changeList() {
    let sido = $("#sido-select option:selected").val();
    let goongu = $("#goongu-select option:selected").val();
    let charger_type = $("#charger-type-select option:selected").val();
    let service_key = "9M8RlzGjEBytmr26QmyfZo6TNf8VWA3tam6rQdDIycBpeN3Umfqhx8owEj5%2FjjJuNV8jNq9U75seLJLKjRSm5A%3D%3D";
    let zcode;
    let zscode;

    if (sido == "") {
        zcode = "";
    } else {
        zcode = "&zcode=" + sido;
    }

    if (goongu == "") {
        zscode = "";
    } else {
        zscode = "&zscode=" + goongu;
    }

    $.ajax({
        url: "http://apis.data.go.kr/B552584/EvCharger/getChargerInfo?serviceKey=" + service_key + "&numOfRows=30&pageNo=1" + zcode + zscode + "&dataType=JSON",
        dataType: "json",
        method: "GET",
        data: {},

        success: function (response, data) {
            let chargers = response.items;

            if (charger_type != "") {
                for (let x = 0; x < chargers.item.length; x++) {
                    if (parseInt(chargers.item[x].chgerType) != parseInt(charger_type)) {
                        chargers.item.splice(x, 1);
                        x--;
                    }
                }
            }


            console.log(chargers.item);
            if (Array.isArray(chargers.item) && chargers.item.length === 0) {
                alert("일치하는 충전소가 없습니다");
            }


            let charger_bundle = chargers.item.reduce((result, item) => {
                let {statId} = item;
                if (result[statId] === undefined) {
                    result[statId] = [];
                }
                result[statId].push(item);
                return result;

            }, {});

            console.log(charger_bundle);
            for (var q in charger_bundle) {
                for (var value of charger_bundle[q]) {
                }
            }

            let charger_keys = Object.keys(charger_bundle);

            let result_list_html = "";

            for (let n = 0; n < posmarkers.length; n++) {
                posmarkers[n].setMap(null);
                posinfowindow[n].close();
            }
            posmarkers = [];
            posinfowindow = [];

            function panTo() {
                // 이동할 위도 경도 위치를 생성합니다
                var moveLatLon = new kakao.maps.LatLng(charger_bundle[charger_keys[0]][0].lat, charger_bundle[charger_keys[0]][0].lng);
                infowindow.close();
                // 지도 중심을 부드럽게 이동시킵니다
                // 만약 이동할 거리가 지도 화면보다 크면 부드러운 효과 없이 이동합니다
                map.panTo(moveLatLon);
            }

            var position = [];


            for (let k = 0; k < charger_keys.length; k++) {
                var gb_position = {
                    content: `<div class="ifw"><h5>${charger_bundle[charger_keys[k]][0].statNm}</h5><h6>${charger_bundle[charger_keys[k]][0].addr}</h6>`,
                    latlng: new kakao.maps.LatLng(charger_bundle[charger_keys[k]][0].lat, charger_bundle[charger_keys[k]][0].lng)
                }
                position.push(gb_position)

                result_list_html += `<div class='result-box' id='${charger_bundle[charger_keys[k]][0].statId}'>`;
                result_list_html += `<div class='charge-name'>${charger_bundle[charger_keys[k]][0].statNm}</div>`;
                result_list_html += `<div class='business-tel'>T. ${charger_bundle[charger_keys[k]][0].busiCall}</div>`;
                result_list_html += `<div class='charge-adress'>주소 : ${charger_bundle[charger_keys[k]][0].addr}</div>`;
                result_list_html += `<div class='business-name'>기관 : ${charger_bundle[charger_keys[k]][0].bnm}</div>`;
                result_list_html += `<div class='use-time'>사용 시간 : ${charger_bundle[charger_keys[k]][0].useTime}</div></div>`;
                result_list_html += `<button class='detail-button' id='detail-button-${charger_bundle[charger_keys[k]][0].statId}' onclick="showDetail(${charger_bundle[charger_keys[k]][0].statId})">상세보기</button>`;
                result_list_html += `<div class='detail-box' id='detail-box-${charger_bundle[charger_keys[k]][0].statId}' style='border:solid 1px black; padding:20px 3px; display: none;'>`;

                for (let n = 0; n < charger_bundle[charger_keys[k]].length; n++) {
                    result_list_html += `<div>${n + 1}번  ${charge_type[charger_bundle[charger_keys[k]][n].chgerType]} : ${charge_state[charger_bundle[charger_keys[k]][n].stat]}</div>`;
                }
                result_list_html += "</div>";
            }

            for (var i = 0; i < position.length; i++) {

                // 마커를 생성합니다
                var marker = new kakao.maps.Marker({
                    map: map, // 마커를 표시할 지도
                    position: position[i].latlng, // 마커를 표시할 위치

                });
                var iwContent = `<div style="padding:7px;">${charger_bundle[charger_keys[i]][0].statNm}<br>${charger_bundle[charger_keys[i]][0].addr}</div>`, // 인포윈도우에 표출될 내용으로 HTML 문자열이나 document element가 가능합니다
                    iwPosition = new kakao.maps.LatLng(charger_bundle[charger_keys[i]][0].lat, charger_bundle[charger_keys[i]][0].lng); //인포윈도우 표시 위치입니다

                // 인포윈도우를 생성합니다
                var infowindow = new kakao.maps.InfoWindow({
                    position: iwPosition,
                    content: iwContent
                });
                posinfowindow.push(infowindow);
                posmarkers.push(marker);
                posinfowindow[i].open(map, marker);
            }

            panTo();
            document.getElementById("list").innerHTML = result_list_html;
        },
        error: function (request, status, error) {
            alert("실패");
            console.log(error);
        },
        complete: function () {
            console.log("성공");
        }
    });
}