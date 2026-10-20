package shop;

import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.GetMapping;

@FeignClient(name = "products", url = "${products.url}")
public interface ProductClient {
    @GetMapping("/products/{id}")
    String getProduct(String id);
}
