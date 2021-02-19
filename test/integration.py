from selenium import webdriver
from selenium.webdriver.common.keys import Keys

# We are assuming that the following has already been done:
# docker-compose -f docker-compose-test.yml down
# docker-compose -f docker-compose-test.yml up --force-recreate --build -d
# docker-compose -f docker-compose-test.yml exec django ./site_init.sh

driver = webdriver.Firefox()
driver.get("http://localhost:18080/ftc")

# Click Join button (maybe we should log out first?)
join_button = driver.find_element_by_css_selector("a.btn-success")
join_button.click()

# Fill in details
test_email_address = "tester@test.com"
test_user_id = "tester"
driver.find_element_by_id("id_username").send_keys(test_user_id)
driver.find_element_by_id("id_email").send_keys(test_email_address)
driver.find_element_by_id("id_password1").send_keys("MyPaSsW0rd")
driver.find_element_by_id("id_password2").send_keys("MyPaSsW0rd")
driver.find_element_by_class_name("btn-primary").click()

# Check that we are on the verify page now
assert "Verify" in driver.title
info = driver.find_element_by_css_selector("div.alert-info")
assert test_email_address in info.text

# Check webmail
driver.get("http://localhost:18081/")

# Click on the first link in the first email we see, that's what I always do
driver.find_element_by_css_selector("td.body-text p a").click()

# Does this display the correct message?
assert test_user_id in driver.find_element_by_css_selector("p.lead span.lead").text
assert test_email_address in driver.find_element_by_css_selector("p.lead > a").text

# This is correct! Click "confirm"
driver.find_element_by_css_selector("button.btn-success").click()

driver.close()
