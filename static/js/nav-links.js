function fillNav() {
    $("#nav-links").html("");
    $.ajax({
        url: '/api/pages',
        type: 'GET',
        success: function (response) {
            for (const [key, value] of Object.entries(response)) {
                $("#nav-links").append(`    
            <li><a href="${key}" class="nav-link">${value}</a></li>
                `);
            };
        },
        error: function (xhr, status, error) {
            console.error('Failed to fetch car data:', error);
        }
    });
}