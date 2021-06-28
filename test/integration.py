import unittest
from selenium import webdriver
from selenium.webdriver.common.alert import Alert
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
import subprocess
import time
import glob
import os
import base64

def retrying(retries, f, delay=1):
    if retries == 1:
        return f()
    else:
        try:
            return f()
        except:
            time.sleep(delay)
            return retrying(retries - 1, f)


class DockerCompose:
    def __init__(self, yml):
        if yml:
            self.pre = ["docker-compose", "-f", yml]
        else:
            self.pre = ["docker-compose"]

    def down(self):
        subprocess.run(self.pre + ["down"])
        return self

    def up(self):
        subprocess.run(self.pre + ["up", "--force-recreate", "--build", "-d"])
        return self

    def exec(self, *kargs):
        subprocess.run(self.pre + ["exec", "django"] + list(kargs))
        return self

    def init(self):
        self.exec("./site_init.sh")
        return self


class BasePage:
    def __init__(self, driver):
        self.driver = driver

    def fill_form(self, fields):
        for k,v in fields.items():
            elt = self.driver.find_element_by_css_selector('*[name="{0}"]'.format(k))
            if type(v) is bool:
                if v != elt.is_selected():
                    elt.click()
            else:
                if elt.tag_name.lower() == 'select':
                    elt.click()
                    opt = elt.find_element_by_css_selector('option[value="{0}"]'.format(v))
                    assert opt
                    opt.click()
                else:
                    elt.clear()
                    elt.send_keys(v)

    def submit(self):
        url = self.driver.current_url
        self.driver.find_element_by_css_selector('input[type="submit"]').click()
        return url != self.driver.current_url


class WebMail(BasePage):
    def go(self):
        self.driver.get("http://localhost:18081/")
        return self

    def click_first_body_link(self):
        self.driver.find_element_by_css_selector("td.body-text p a").click()


class HomePage(BasePage):
    def go(self):
        self.driver.get("http://localhost:18080/ftc")
        return self

    def join(self):
        self.driver.find_element_by_css_selector("a.btn-success").click()
        return JoinPage(self.driver)


class User:
    def __init__(self, identity, email, password):
        self.identity = identity
        self.email = email
        self.password = password


class JoinPage(BasePage):
    def check(self):
        assert "Signup" in self.driver.title
        return self

    def fill_in(self, user):
        self.driver.find_element_by_id("id_username").send_keys(user.identity)
        self.driver.find_element_by_id("id_email").send_keys(user.email)
        self.driver.find_element_by_id("id_password1").send_keys(user.password)
        self.driver.find_element_by_id("id_password2").send_keys(user.password)
        self.driver.find_element_by_class_name("btn-primary").click()
        return VerifyPage(self.driver)


class VerifyPage(BasePage):
    def check(self, user):
        assert "Verify" in self.driver.title
        info = self.driver.find_element_by_css_selector("div.alert-info")
        assert user.email in info.text
        return self


class ConfirmPage(BasePage):
    def check(self, user):
        assert user.identity in self.driver.find_element_by_css_selector("p.lead span.lead").text
        assert user.email in self.driver.find_element_by_css_selector("p.lead > a").text
        return self

    def confirm(self):
        self.driver.find_element_by_css_selector("button.btn-success").click()
        return SignInPage(self.driver)


class SignInPage(BasePage):
    def go(self):
        self.driver.get("http://localhost:18080/accounts/login")
        return self

    def sign_in(self, user):
        self.driver.find_element_by_css_selector('input[name="login"]').send_keys(user.identity)
        self.driver.find_element_by_css_selector('input[name="password"]').send_keys(user.password)
        self.driver.find_element_by_class_name("btn-primary").click()
        return ProfilePage(self.driver)


class ProfilePage(BasePage):
    def login_name(self):
        return self.driver.find_element_by_class_name('fa-user').text

    def go_start_counting(self):
        self.driver.find_element_by_id("start-counting-link").click()
        return CountingPage(self.driver)


class CountingPage(BasePage):
    def check(self):
        self.driver.find_element_by_id("btn-tracknum")
        return self

    def go(self):
        self.driver.get("http://localhost:18080/ftc/counting")
        return self

    def count(self):
        return self.driver.execute_script(
            'return document.getElementById("tracknum").value;')

    def assert_count(self, count):
        c = self.count()
        assert c == count, "Count should be '{0}' but is '{1}'".format(count, c)

    def check_count(self, count):
        retrying(
            6,
            lambda: self.assert_count(count),
            0.3
        )

    def click_at(self, x, y):
        mp = self.driver.find_element_by_id("map")
        lil = mp.find_element_by_css_selector('img.leaflet-image-layer')
        actions = ActionChains(self.driver)
        actions.move_to_element_with_offset(lil,
            x * lil.size["width"], y * lil.size["height"])
        actions.click().pause(1.0).perform()
        return self

    def delete_from(self, minx, maxx, miny, maxy):
        self.driver.find_element_by_id("ftc-btn-select").click()
        mp = self.driver.find_element_by_id("map")
        lil = mp.find_element_by_css_selector('img.leaflet-image-layer')
        w = lil.size["width"]
        h = lil.size["height"]
        actions = ActionChains(self.driver)
        actions.move_to_element_with_offset(lil, minx * w, miny * h)
        actions.click().pause(0.1)
        actions.move_to_element_with_offset(lil, maxx * w, maxy * h)
        actions.click().pause(0.1).perform()
        self.driver.find_element_by_id("ftc-btn-delete").click()
        return self

    def dismiss_well_done_message(self):
        retrying(3, lambda: Alert(self.driver).accept())
        return self

    def submit(self):
        self.driver.find_element_by_id("btn-tracknum").click()
        self.driver.find_element_by_id("tracknum-submit").click()
        Alert(self.driver).accept()
        self.dismiss_well_done_message()

    def save(self):
        self.driver.find_element_by_id("btn-tracknum").click()
        self.driver.find_element_by_id("tracknum-save").click()
        Alert(self.driver).accept()
        return self

    def drag_layer_handle(self, offset):
        track = self.driver.find_element_by_id("slider2")
        dy = offset * track.size['height']
        handle = self.driver.find_element_by_class_name("noUi-touch-area")
        actions = ActionChains(self.driver)
        actions.drag_and_drop_by_offset(handle, 0, dy).pause(1.0).perform()
        return self

    def image_displayed_url(self):

        class ElementsLoaded:
            def __init__(self, locator_type, locator_string, count):
                self.locator_type = locator_type
                self.locator_string = locator_string
                self.count = count
            def __call__(self, driver):
                es = driver.find_elements(self.locator_type, self.locator_string)
                if len(es) < self.count:
                    return False
                return es

        images = WebDriverWait(self.driver, 3).until(
            ElementsLoaded(By.CLASS_NAME, "leaflet-image-layer", 4))

        return images[-1].get_attribute("src")


class NavBar(BasePage):
    def get_dropdown(self):
        return self.driver.find_element_by_css_selector(
            ".navbar-fixed-top .navbar-right a.dropdown-toggle"
        )

    def check(self):
        self.get_dropdown()
        return self

    def logout(self):
        self.get_dropdown().click()
        self.driver.find_element_by_css_selector(
            'a[href="/accounts/logout/"]'
        ).click()
        return HomePage(self.driver)

    def go_manage_projects(self):
        self.get_dropdown().click()
        self.driver.find_element_by_css_selector(
            'a[href="/ftc/report/"]'
        ).click()
        return ReportPage(self.driver)

    def go_edit_projects(self):
        self.get_dropdown().click()
        self.driver.find_element_by_id('projects-link').click()
        return ProjectsPage(self.driver)


class ReportPage(BasePage):
    def toggle_tree_node(self, name):
        self.driver.find_element_by_xpath(
            "//span[@class='fancytree-title' and text()='"
            + name
            + "']//preceding-sibling::span[@class='fancytree-expander']"
        ).click()
        return self

    def select_tree_node(self, name):
        self.driver.find_element_by_xpath(
            "//span[@class='fancytree-title' and text()='"
            + name
            + "']//preceding-sibling::span[@class='fancytree-checkbox']"
        ).click()
        return self

    def result_now(self, grain_number):
        rows = self.driver.find_elements(By.CSS_SELECTOR, "#mytable tbody tr")
        for r in rows:
            tds = r.find_elements(By.CSS_SELECTOR, "td")
            if 5 <= len(tds) and tds[2].text == grain_number:
                return tds[4].text
        return None

    def result_or_fail(self, grain_number):
        r = self.result_now(grain_number)
        assert r != None, "Grain number {0} not in table".format(grain_number)
        return r

    def result(self, grain_number):
        return retrying(4, lambda: self.result_or_fail(grain_number), 0.1)


class ProjectsPage(BasePage):
    def create_project(self):
        self.driver.find_element_by_id('create-project').click()
        return ProjectCreatePage(self.driver)


class ProjectCreatePage(BasePage):
    def create(self, name, description, priority, closed):
        self.fill_form({
            'project_name': name,
            'project_description': description,
            'priority': priority,
            'closed': closed
        })
        assert self.submit()
        return ProjectPage(self.driver)


class ProjectPage(BasePage):
    def create_sample(self):
        self.driver.find_element_by_id('create-sample').click()
        return SampleCreatePage(self.driver)


class SampleCreatePage(BasePage):
    def create(self, name, property_, priority, min_contributor_num, completed):
        self.fill_form({
            'sample_name': name,
            'sample_property': property_,
            'priority': priority,
            'min_contributor_num': min_contributor_num,
            'completed': completed
        })
        assert self.submit()
        return SamplePage(self.driver)


class SamplePage(BasePage):
    def create_grain(self):
        self.driver.find_element_by_id('create-grain').click()
        return GrainCreatePage(self.driver)


class GrainCreatePage(BasePage):
    def create(self, paths):
        browse = self.driver.find_element_by_id('id_images')
        for p in paths:
            browse.send_keys(p)
        assert self.submit()
        return GrainPage(self.driver)


class GrainPage(BasePage):
    def edit(self):
        zoom_outs = self.driver.find_elements_by_class_name('leaflet-control-zoom-out')
        assert len(zoom_outs) == 1
        imgs = self.driver.find_elements_by_css_selector('img.leaflet-image-layer')
        while (600 < imgs[0].rect['width']
                and 'leaflet-disabled' not in
                zoom_outs[0].get_attribute('class').split(' ')):
            zoom_outs[0].click()
        self.driver.find_element_by_id('edit').click()
        return self

    def save(self):
        self.driver.find_element_by_id('save').click()
        return self

    def do_drag(self, dragee, dest_x, dest_y):
        ActionChains(self.driver).click_and_hold(dragee).perform()
        for n in range(3):
            drag_x_by = dest_x - (
                dragee.rect['x'] + dragee.rect['width']/2)
            drag_y_by = dest_y - (
                dragee.rect['y'] + dragee.rect['height'])
            ActionChains(self.driver).move_by_offset(
                drag_x_by, drag_y_by
            ).perform()
        ActionChains(self.driver).release().perform()

    def drag_marker(self, marker_index, to_x, to_y):
        imgs = self.driver.find_elements_by_css_selector('img.leaflet-image-layer')
        rect = imgs[0].rect
        markers = self.driver.find_elements_by_css_selector(
            'img.leaflet-marker-icon')
        marker = markers[marker_index]
        self.do_drag(
            marker,
            to_x * rect['width'] + rect['x'],
            to_y * rect['height'] + rect['y']
        )
        return self


class ScriptUploader:
    def __init__(self, driver):
        self.driver = driver

    def upload_projects(self, directory):
        self.dc.exec("python3", "upload_projects.py",
            "-s", "geochron.settings",
            "-i", directory,
        )

    def get_index(self, file_url):
        src = file_url.rstrip("/")
        index = src.rfind("/") + 1
        return int(src[index:])


class WebUploader:
    def __init__(self, driver):
        self.driver = driver
        self.script="""
        var url=arguments[0];
        var done=arguments[1];
        var x=new XMLHttpRequest();
        x.open("GET", url);
        x.responseType="arraybuffer";
        x.onload=function() {
            var r=new Uint8Array(x.response);
            var b='';
            var n=r.byteLength;
            for(var i=0;i<n;++i){
                b+=String.fromCharCode(r[i]);
            }
            done(b);
        };
        x.send();
        """

    def upload_projects(self, directory):
        crystal_path = os.path.abspath(directory + '/*/*/*/*/*.jpg')
        files = glob.glob(crystal_path)
        self.hashes = {}
        for f in files:
            number = int( f[ f.rindex('-') + 1 : f.rindex('.') ] )
            with open(f, 'rb') as h:
                contents = h.read()
                hash_ = hash(contents)
                self.hashes[hash_] = number
        navbar = NavBar(self.driver)
        edit_projects = navbar.go_edit_projects()
        project_page = edit_projects.create_project().create('p1', 'description', 1, False)
        sample_page = project_page.create_sample().create('s1', 'T', 1, 1, False)
        grain_page = sample_page.create_grain().create(files)
        grain_page.edit()
        grain_page.drag_marker(0, 0.01, 0.01)
        grain_page.drag_marker(1, 0.01, 0.99)
        grain_page.drag_marker(3, 0.99, 0.01)
        grain_page.drag_marker(2, 0.01, 0.99) # delete by dragging onto 3
        grain_page.save()

    def get_index(self, file_url):
        ba = self.driver.execute_async_script(self.script, file_url)
        hash_ = hash(ba)
        return self.hashes.get(hash_)


class DjangoTests(unittest.TestCase):
    def setUp(self):
        self.dc = DockerCompose("./docker-compose-test.yml").down().up().init()
        self.driver = webdriver.Firefox()

    def test_onboard(self):
        # Upload Crystal images
        test_user = User("tester", "tester@test.com", "MyPaSsW0rd")
        project_user = User("john", "john@test.com", "john")
        HomePage(self.driver).go()
        profile = SignInPage(self.driver).go().sign_in(project_user)
        uploader = WebUploader(self.driver)
        #uploader = new ScriptUploader(self.driver)
        uploader.upload_projects('test/crystals')
        navbar = NavBar(self.driver)
        navbar.logout()

        # create user
        join_page = HomePage(self.driver).go().join()
        join_page.check().fill_in(test_user).check(test_user)
        WebMail(self.driver).go().click_first_body_link()
        ConfirmPage(self.driver).check(test_user).confirm()

        # sign in as this new user
        profile = SignInPage(self.driver).go().sign_in(test_user)

        # start counting tracks
        counting = profile.go_start_counting().check()
        self.assertEqual(uploader.get_index(counting.image_displayed_url()), 1)
        self.assertEqual(uploader.get_index(counting.drag_layer_handle(0.33).image_displayed_url()), 2)
        self.assertEqual(uploader.get_index(counting.drag_layer_handle(0.67).image_displayed_url()), 4)
        self.assertEqual(uploader.get_index(counting.drag_layer_handle(-0.33).image_displayed_url()), 3)
        counting.check_count("000")
        counting.click_at(0.6, 0.35)
        counting.check_count("001")
        counting.click_at(0.45, 0.5)
        counting.check_count("002")
        # this one is outside of the boundary
        counting.click_at(0.55, 0.55)
        counting.check_count("002")
        counting.click_at(0.52, 0.37)
        counting.check_count("003")
        counting.click_at(0.37, 0.52)
        counting.check_count("004")
        # delete one
        counting.delete_from(0.51, 0.59, 0.33, 0.41)
        counting.check_count("003")

        # save intermediate result and logout
        counting.save()
        navbar.logout()

        # login, check no results yet
        profile = SignInPage(self.driver).go().sign_in(project_user)
        report = navbar.go_manage_projects()
        report.toggle_tree_node("p1")
        report.select_tree_node("s1")
        # Should be no grain "1" in the table yet
        # (as it is a partial save, not a submission)
        self.assertRaises(AssertionError, report.result, "1")
        # start counting, logout
        counting.go().dismiss_well_done_message().check_count("000")
        navbar.check().logout()

        # login as test user, we should still see the saved result
        profile = SignInPage(self.driver).go().sign_in(test_user)
        counting = profile.go_start_counting().check()
        counting.check_count("003")

        # submit the result
        counting.submit()

        # see this result, as project admin
        navbar.logout()
        profile = SignInPage(self.driver).go().sign_in(project_user)
        report = navbar.go_manage_projects()
        report.toggle_tree_node("p1")
        report.select_tree_node("s1")
        self.assertEqual(report.result("1"), "3")

    def tearDown(self):
        self.driver.close()
        self.dc.down()


if __name__ == '__main__':
    unittest.main()
