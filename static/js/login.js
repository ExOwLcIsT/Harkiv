function deleteCookie(name) {
    document.cookie = name + '=; Max-Age=0; path=/;';
}

function showlogin() {
    $("#login").css('visibility', 'visible');
}

function logout() {
    deleteCookie('username');
    $("#logout").css("visibility", "hidden");
    $("#showlog").css("visibility", "visible");
    window.location.reload(true);
}

function showsignupform() {
    $("#signupform").css("visibility", "visible");
    $("#loginform").css("visibility", "hidden");
}

function showloginform() {
    $("#signupform").css("visibility", "hidden");
    $("#loginform").css("visibility", "visible");
}

function signup(event) {
    event.preventDefault();
    if ($("#signuppassword").val() !== $("#confirmpassword").val()) {
        alert("Passwords do not match!");
        return;
    }

    let formData = new FormData(document.getElementById('signupform'));

    $.ajax({
        url: `/authorize/signup`,
        method: "POST",
        data: formData,
        processData: false,
        contentType: false,
        success: function (response) {
            if (response.success) {
                alert("Registration successful!");
                document.cookie = `username=${response.login}; path=/;`;
                $("signupform").css("visibility", "hidden");
                $("#logout").css("visibility", "visible");
                $("#showlog").css("visibility", "hidden");
                $("#login").css('visibility', 'hidden ');
                window.location.reload(true);
            } else {
                alert(response.message);
            }
        },
        error: function () {
            alert("An error occurred during registration!");
        }
    });
}

function login(event) {
    event.preventDefault();
    $.ajax({
        async: true,
        url: `/authorize/login`,
        method: "POST",
        headers: {
            "Content-Type": "application/x-www-form-urlencoded"
        },
        data: {
            login: $("#loginusername").val(),
            password: $("#loginpassword").val()
        },
        success: function (response) {
            if (response) {
                console.log(response)
                document.cookie = `username=${response.login}; path=/;`;
                alert("Логін успішний!");
                $("#logout").css("visibility", "visible");
                $("#showlog").css("visibility", "hidden");
                $("#login").css('visibility', 'hidden ');
                window.location.reload(true);
            } else {
                alert("Невірний логін або пароль!");
            }
        },
        error: function (err) {
            console.error(err)
            alert("Сталася помилка під час авторизації!");
        }
    });
}

function forgotPassword() {
    $.ajax({
        async: true,
        url: `/api/password/${$("#loginusername").val()}`,
        method: "GET",
        headers: {
            "Content-Type": "application/json"
        },
        success: function (response) {
            if (response) {
                $("#forgottenPassword").html(response);
            } else {
                alert("Сталася помилка!");
            }
        },
        error: function (err) {
            console.error(err)
            alert("Сталася помилка!");
        }
    });
}