package shop;

public class OrderController {
    private final OrderService orders;

    public OrderController(OrderService orders) {
        this.orders = orders;
    }

    public String place(String id) {
        return orders.placeOrder(id);
    }
}
