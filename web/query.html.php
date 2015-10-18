<?php

function html($text) {
    return htmlspecialchars($text, ENT_QUOTES|ENT_HTML5, 'UTF-8');
}

$host = $_SERVER['DB_HOST'];
$user = $_SERVER['DB_USER'];
$password = $_SERVER['DB_PASSWORD'];
$schema = $_SERVER['DB_SCHEMA'];

$mysqli = new mysqli($host, $user, $password, $schema);
if ($mysqli->connect_errno) {
    header("HTTP/1.0 500 Internal Server Error");
    echo("500 Internal Server Error\n");
    echo("Failed to connect to database: ".$mysqli->connect_error);
    die();
}

if (!array_key_exists('query', $_GET) || $_GET['query'] === '') {
    $query = "SELECT t, COUNT(*) FROM message GROUP BY t ORDER BY t";
} else {
    $query = $_GET['query'];
}

$fields = array();
$error = false;
if ($res = $mysqli->query($query, MYSQLI_USE_RESULT)) {
    $fno = 0;
    while ($finfo = $res->fetch_field()) {
        $fields[] = array(
            "index" => $fno++,
            "name" => $finfo->name,
            "type" => $finfo->type,
        );
    }

    $rows_fetched = 0;
    while ($rows_fetched < 1000) {
        if (($row = $res->fetch_row()) !== null) {
            $dataset[] = $row;
            $rows_fetched++;
        } else {
            break;
        }
    }

    if ($rows_fetched === 0) {
        $error = "Query returned an empty set of results.";
    }

    $result_limited = $rows_fetched === 1000 && $res->fetch_row() !== null;
} else {
    $error = $mysqli->error;
}

$mysqli->close();

?>
<!DOCTYPE html>
<html>
    <head>
        <meta charset="UTF-8">
        <title>Discord WebSocket Log</title>

        <!-- At least it's better than unstyled HTML... -->
        <link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.5/css/bootstrap.min.css">
        <script src="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.5/js/bootstrap.min.js"></script>

        <link rel="stylesheet" href="style">
    </head>
    <body>
        <div class="container-fluid">
            <h1>Discord WebSocket Log</h1>
            <p>A simple discord WebSocket message log, for API debugging and reference purpose.

            <form class="form-inline" method="GET" action="query" accept-charset="UTF-8">
                <div class="form-group" id="query-box">
                    <input type="text" class="form-control" name="query" value="<?=html($query)?>">
                </div>
                <button type="submit" id="query-button" class="btn btn-default">Run MySQL Query</button>
            </form>
<?php
if ($result_limited) { ?>
            <div class="alert alert-info">
                <strong>Note:</strong> Only the first 1000 results of the query is shown.
            </div>
<?php
}

if ($error !== false) { ?>
            <div class="alert alert-danger">
                <?=html($error)?>
            </div>
<?php
} else { ?>
            <table class="table">
                <tr>
<?php
    foreach ($fields as $field) { ?>
                    <th title="<?=html($field["type"])?>"><?=html($field["name"])?></th>
<?php
} ?>
                </tr>
<?php

    foreach ($dataset as $row) { ?>
                <tr>
<?php
        foreach ($fields as $field) {
            $value = $row[$field["index"]];
            if ($value === null) { ?>
                    <td class="sql-null">NULL</td>
<?php
            } else if ($field["name"] === "raw") {
                $decoded = json_decode($value);
                if ($decoded !== null) {
                    $value = json_encode($decoded, JSON_PRETTY_PRINT);
                } else {
                    $value = implode("\n", str_split($value, 80));
                } ?>
                    <td>
<pre><?=html($value)?></pre>
                    </td>
<?php
            } else {
                if ($field["name"] === "dir") {
                    if ($value === "0") {
                        $value = "Receive";
                    } else if ($value === "1") {
                        $value = "Send";
                    }
                } ?>
                    <td><?=html($value)?></td>
<?php
            }
        } ?>
                </tr>
<?php
    }
} ?>
            </table>
        </div>
    </body>
</head>
