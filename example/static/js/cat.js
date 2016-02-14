var count_down;
var total_time;
function set_time(){
    if(count_down == 0){
        $(".modal").modal({backdrop: "static", "keyboard": false});
    }else{
        count_down--;
        var progress_val = count_down / total_time * 100 | 0;
        $(".time-bar").css("width", progress_val + '%');
        $(".time").text(count_down + "秒")
    }
}
setInterval(function(){set_time();}, 1000);
$(function () {
    count_down = parseInt($("#count-down").text());
    total_time = count_down;
    var total_item = parseInt($("#total").text());
    var item_no = parseInt($("#current").text());
    var progress_val = item_no / total_item * 100 | 0;
    $(".item-bar").css("width", progress_val + '%').attr("aria-valuenow", parseInt(progress_val));
    $(".progress-item").tooltip({
        trigger: "hover focus",
        title: "还剩" + (total_item - item_no) + "题",
        placement: "left", container: "body"
    });
    $(".list-choice").click(function () {
        $(".list-choice-checked").removeClass("list-choice-checked");
        $(this).addClass("list-choice-checked");
        var val = $(this).attr("id");
        $("input[name=question]").attr('value', val);
        $(".btn").tooltip('destroy')
    });
    $(".btn-block").click(function () {
        var val = $("input[name=question]").val();
        if (val != "") {
            document.forms[0].submit()
        }
    }).tooltip({
        trigger: "hover focus",
        title: "请先勾选选项",
        placement: "left",
        container: "body"
    });
    $(".well").popover({
        trigger: "hover",
        content: $("#que").text(),
        placement: "right",
        container: "body"
    });
    $(".list-choice-group").popover({
        trigger: "hover",
        content: $("#choice").html(),
        placement: "left",
        container: "body"
    });
    $(".btn-sm").click(function(){
        document.forms[0].submit()
    });
    $(".finished").popover({
        trigger: "hover",
        content: "已完成,点击查看结果",
        placement: "right",
        container: "body"
    })
});