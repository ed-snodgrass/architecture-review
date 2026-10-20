package shop;

import feign.FeignException;

public class OrderService {
    private final ProductClient products;

    public OrderService(ProductClient products) {
        this.products = products;
    }

    public String placeOrder(String id) {
        try {
            return products.getProduct(id);
        } catch (FeignException failure) {
            throw failure;
        }
    }
}
