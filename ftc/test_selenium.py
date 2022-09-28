from django.test import Client, tag, TestCase
from pathlib import Path
from selenium import webdriver
from selenium.common import exceptions
from selenium.webdriver.common.alert import Alert
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
import base64
import glob
import os
import subprocess
import tempfile
import time

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


def maybe_click(elt):
    if elt is None:
        return False
    elt.click()
    return True

class BasePage:
    def __init__(self, driver):
        self.driver = driver

    def check(self):
        return True

    def wait(self):
        """
        Wait until check() passes
        """
        WebDriverWait(self.driver, timeout=3).until(
            lambda d: self.check()
        )

    def fill_form(self, fields):
        for k,v in fields.items():
            elt = self.driver.find_element(By.CSS_SELECTOR,  '*[name="{0}"]'.format(k))
            if type(v) is bool:
                if v != elt.is_selected():
                    elt.click()
            else:
                if elt.tag_name.lower() == 'select':
                    elt.click()
                    opt = elt.find_element(By.CSS_SELECTOR,  'option[value="{0}"]'.format(v))
                    assert opt
                    opt.click()
                else:
                    elt.clear()
                    elt.send_keys(v)

    def submit(self):
        url = self.driver.current_url
        self.driver.find_element(By.CSS_SELECTOR,  'input[type="submit"]').click()
        return url != self.driver.current_url

    def element_is_disabled(self, elt):
        if type(elt) is str:
            elt = self.driver.find_element(By.ID, elt)
        return 'leaflet-disabled' in elt.get_attribute('class').split(' ')

    def scroll_into_view(self, elt):
        r = elt.rect
        wr = self.driver.get_window_rect()
        js = 'window.scroll({0},{1})'.format(
            r['x'] + (r['width'] - wr['width'])/2,
            r['y'] + (r['height'] - wr['height'])/2
        )
        self.driver.execute_script(js)

    def find_by_id(self, id):
        return WebDriverWait(self.driver, timeout=2).until(
            lambda d: d.find_element(By.ID, id)
        )

    def find_by_css(self, css):
        return WebDriverWait(self.driver, timeout=2).until(
            lambda d: d.find_element(By.CSS_SELECTOR, css)
        )

    def click_element(self, locator, css):
        WebDriverWait(
            self.driver,
            timeout=2,
            ignored_exceptions=[
                exceptions.StaleElementReferenceException,
                exceptions.ElementNotInteractableException
            ]
        ).until(
            lambda d: maybe_click(d.find_element(locator, css))
        )

    def click_by_id(self, id):
        self.click_element(By.ID, id)

    def click_by_css(self, css):
        self.click_element(By.CSS_SELECTOR, css)


class WebMail(BasePage):
    def go(self):
        self.driver.get("http://localhost:18081/")
        return self

    def click_first_body_link(self):
        self.driver.find_element(By.CSS_SELECTOR,  "td.body-text p a").click()


class HomePage(BasePage):
    def go(self):
        self.driver.get("http://localhost:18080/ftc")
        return self

    def join(self):
        self.driver.find_element(By.CSS_SELECTOR,  "a.btn-success").click()
        return JoinPage(self.driver)

    def become_guest(self):
        # log on as guest. ProfilePage is returned, which will be wrong if
        # the guest has already done the tutorial (then it will be CountingPage)
        self.driver.get("http://localhost:18080/ftc/counting/guest")
        return ProfilePage(self.driver)


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
        self.driver.find_element(By.ID, "id_username").send_keys(user.identity)
        self.driver.find_element(By.ID, "id_email").send_keys(user.email)
        self.driver.find_element(By.ID, "id_password1").send_keys(user.password)
        self.driver.find_element(By.ID, "id_password2").send_keys(user.password)
        self.driver.find_element(By.CLASS_NAME, "btn-primary").click()
        return VerifyPage(self.driver)


class VerifyPage(BasePage):
    def check(self, user):
        assert "Verify" in self.driver.title
        info = self.driver.find_element(By.CSS_SELECTOR,  "div.alert-info")
        assert user.email in info.text
        return self


class ConfirmPage(BasePage):
    def check(self, user):
        assert user.identity in self.driver.find_element(By.CSS_SELECTOR,  "p.lead span.lead").text
        assert user.email in self.driver.find_element(By.CSS_SELECTOR,  "p.lead > a").text
        return self

    def confirm(self):
        self.driver.find_element(By.CSS_SELECTOR,  "button.btn-success").click()
        return SignInPage(self.driver)


class SignInPage(BasePage):
    def go(self):
        self.driver.get("http://localhost:18080/accounts/login")
        return self

    def sign_in(self, user):
        self.driver.find_element(By.CSS_SELECTOR,  'input[name="login"]').send_keys(user.identity)
        self.driver.find_element(By.CSS_SELECTOR,  'input[name="password"]').send_keys(user.password)
        self.driver.find_element(By.CLASS_NAME, "btn-primary").click()
        return ProfilePage(self.driver)


class TutorialPage(BasePage):
    def check_text_contains(self, text):
        tut_text = self.driver.find_element(By.ID, 'results').text
        assert text in tut_text
        return self

    def go_next(self):
        e = self.driver.find_element(By.ID, 'next')
        self.scroll_into_view(e)
        e.click()
        return self

    def go_previous(self):
        self.driver.find_element(By.ID, 'previous').click()
        return self

    def get_finish_link(self):
        return self.driver.find_element(By.ID, 'finish')

    def go_finish(self):
        self.get_finish_link().click()
        return CountingPage(self.driver)

    def get_to_end_and_finish(self):
        while not self.finish_available():
            self.go_next()
        return self.go_finish()

    def finish_available(self):
        link = self.get_finish_link()
        return link.get_attribute('disabled') != 'true'

    def check_finish_available(self):
        link = self.get_finish_link()
        assert link.get_attribute('disabled') != 'true'
        return self

    def check_finish_not_available(self):
        link = self.get_finish_link()
        assert link.get_attribute('disabled') == 'true'
        return self


class ProfilePage(BasePage):
    def login_name(self):
        return self.driver.find_element(By.CLASS_NAME, 'fa-user').text

    def go(self):
        self.driver.get("http://localhost:18080/accounts/profile")
        return self

    def get_counting_link(self):
        return self.find_by_id('start-counting-link')

    def go_start_counting(self):
        self.get_counting_link().click()
        return CountingPage(self.driver)

    def check_can_count(self):
        link = self.get_counting_link()
        danger = self.driver.find_elements(By.CLASS_NAME, 'text-danger')
        assert link.get_attribute('disabled') != 'true'
        assert link.get_attribute('href')
        assert not any(['must finish the tutorial' in e.text for e in danger])
        return self

    def check_cannot_count(self):
        link = self.get_counting_link()
        danger = self.driver.find_elements(By.CLASS_NAME, 'text-danger')
        assert link.get_attribute('disabled') == 'true'
        assert link.get_attribute('href') == None
        assert any(['must finish the tutorial' in e.text for e in danger])
        return self

    def go_tutorial(self):
        self.driver.find_element(By.ID, 'tutorial-link').click()
        return TutorialPage(self.driver)


class CountingPage(BasePage):
    def check(self):
        self.find_by_id('btn-tracknum')
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
            7,
            lambda: self.assert_count(count),
            0.3
        )

    def click_at(self, x, y):
        mp = self.driver.find_element(By.ID, "map")
        lil = mp.find_element(By.CSS_SELECTOR,  'img.leaflet-image-layer')
        actions = ActionChains(self.driver)
        actions.move_to_element_with_offset(lil,
            (x - 0.5) * lil.rect["width"], (y - 0.5) * lil.size["height"])
        actions.click().pause(1.0).perform()
        return self

    def delete_from(self, minx, maxx, miny, maxy):
        self.click_by_id('ftc-btn-select')
        mp = self.driver.find_element(By.ID, "map")
        lil = mp.find_element(By.CSS_SELECTOR,  'img.leaflet-image-layer')
        w = lil.size["width"]
        h = lil.size["height"]
        actions = ActionChains(self.driver)
        actions.move_to_element_with_offset(lil, (minx - 0.5) * w, (miny - 0.5) * h)
        actions.click().pause(1.05)
        actions.move_to_element_with_offset(lil, (maxx - 0.5) * w, (maxy - 0.5) * h)
        actions.click().pause(0.1).perform()
        self.driver.find_element(By.ID, "ftc-btn-delete").click()
        return self

    def undo(self):
        self.driver.find_element(By.ID, "ftc-btn-undo").click()

    def redo(self):
        self.driver.find_element(By.ID, "ftc-btn-redo").click()

    def undo_available(self):
        return not self.element_is_disabled("ftc-btn-undo")

    def redo_available(self):
        return not self.element_is_disabled("ftc-btn-redo")

    def submit(self):
        self.driver.find_element(By.ID, "btn-tracknum").click()
        self.driver.find_element(By.ID, "tracknum-submit").click()
        Alert(self.driver).accept()

    def save(self):
        self.driver.find_element(By.ID, "btn-tracknum").click()
        self.driver.find_element(By.ID, "tracknum-save").click()
        Alert(self.driver).accept()
        return self

    def drag_layer_handle(self, offset):
        track = self.driver.find_element(By.ID, "focus-slider")
        dy = offset * track.size['height']
        handle = self.driver.find_element(By.CLASS_NAME, "noUi-touch-area")
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

        # we used to wait for all four to be loaded, but now it seems only one
        # gets loaded at a time.
        images = WebDriverWait(self.driver, 3).until(
            ElementsLoaded(By.CLASS_NAME, "leaflet-image-layer", 1))

        return images[-1].get_attribute("src")


class NavBar(BasePage):
    def get_dropdown(self):
        return self.find_by_css('#account-dropdown a')

    def click_dropdown(self):
        return self.click_by_css('#account-dropdown a')

    def check(self):
        self.get_dropdown()
        return self

    def logout(self):
        class DropsDown:
            def __init__(self, nav_bar):
                self.nav = nav_bar
            def __call__(self, driver):
                self.nav.click_dropdown()
                logout = driver.find_element(By.CSS_SELECTOR,
                    'a[href="/accounts/logout/"]'
                )
                return logout.is_displayed() and logout
        WebDriverWait(self.driver, 3).until(DropsDown(self)).click()
        return HomePage(self.driver)

    def go_manage_projects(self):
        self.click_dropdown()
        self.driver.find_element(By.CSS_SELECTOR,
            'a[href="/ftc/report/"]'
        ).click()
        return ReportPage(self.driver)

    def go_edit_projects(self):
        self.click_dropdown()
        self.driver.find_element(By.ID, 'projects-link').click()
        return ProjectsPage(self.driver)


class ReportPage(BasePage):
    def toggle_tree_node(self, name):
        self.driver.find_element(By.XPATH,
            "//span[@class='fancytree-title' and text()='"
            + name
            + "']//preceding-sibling::span[@class='fancytree-expander']"
        ).click()
        return self

    def select_tree_node(self, name):
        self.click_element(By.XPATH,
            "//span[@class='fancytree-title' and text()='"
            + name
            + "']//preceding-sibling::span[@class='fancytree-checkbox']"
        )
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
        self.driver.find_element(By.ID, 'create-project').click()
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
        self.driver.find_element(By.ID, 'create-sample').click()
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
        self.driver.find_element(By.ID, 'create-grain').click()
        return GrainCreatePage(self.driver)


class GrainCreatePage(BasePage):
    def create(self, paths):
        browse = self.driver.find_element(By.ID, 'id_uploads')
        for p in paths:
            browse.send_keys(p)
        assert self.submit()
        return GrainPage(self.driver)


def find_best(a, f):
    """
    Returns the element of `a` for which `f` returns the lowest value
    """
    dist = None
    best = None
    for v in a:
        d = f(v)
        if dist is None or d < dist:
            dist = d
            best = v
    return best


def sum_squares(*a):
    """
    Returns the sum of the squares of the elements of `a`
    """
    total = 0
    for x in a:
        total += x * x
    return total


def pin_x(elt):
    return elt.rect['x'] + elt.rect['width'] / 2

def pin_y(elt):
    return elt.rect['y'] + elt.rect['height']


class GrainPage(BasePage):
    def get_image_width(self):
        return WebDriverWait(
            self.driver,
            timeout=2,
            ignored_exceptions=exceptions.StaleElementReferenceException
        ).until(
            lambda d: d.find_element(
                By.CSS_SELECTOR,
                'img.leaflet-image-layer'
            ).rect['width']
        )

    def edit(self):
        zoom_outs = self.driver.find_elements(By.CLASS_NAME, 'leaflet-control-zoom-out')
        assert len(zoom_outs) == 1
        zoom_out = zoom_outs[0]
        while (600 < self.get_image_width()
                and not self.element_is_disabled(zoom_out)):
            zoom_out.click()
        self.driver.find_element(By.ID, 'edit').click()
        return self

    def save(self):
        self.driver.find_element(By.ID, 'save').click()
        return self

    def do_partial_drag(self, dragee, dest_x, dest_y):
        drag_x_by = dest_x - pin_x(dragee)
        drag_y_by = dest_y - pin_y(dragee)
        if -2 < drag_x_by and drag_x_by < 2 and -2 < drag_y_by and drag_y_by < 2:
            return False
        max_distance = 199
        drag_x_by = min(max(drag_x_by, -max_distance), max_distance)
        drag_y_by = min(max(drag_y_by, -max_distance), max_distance)
        ActionChains(self.driver).move_by_offset(drag_x_by, drag_y_by).perform()
        return True

    def do_drag(self, dragee, dest_x, dest_y):
        ActionChains(self.driver).click_and_hold(dragee).perform()
        while self.do_partial_drag(dragee, dest_x, dest_y):
            pass
        ActionChains(self.driver).release().perform()

    def drag_marker(self, from_x_approx, from_y_approx, to_x, to_y):
        img = self.driver.find_element(By.CSS_SELECTOR, 'img.leaflet-image-layer')
        rect = img.rect
        markers = self.driver.find_elements(
            By.CSS_SELECTOR,
            'img.region-vertex-marker'
        )
        marker = find_best(markers, lambda m: sum_squares(
            from_x_approx * rect['width'] + rect['x'] - pin_x(m),
            from_y_approx * rect['height'] + rect['y'] - pin_y(m)
        ))
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
        grain_page.drag_marker(0, 0, 0.01, 0.01)
        grain_page.drag_marker(0, 1, 0.01, 0.99)
        grain_page.drag_marker(1, 0, 0.99, 0.01)
        grain_page.drag_marker(1, 1, 0.01, 0.99) # delete by dragging onto 2nd
        grain_page.save()

    def get_index(self, file_url):
        ba = self.driver.execute_async_script(self.script, file_url)
        hash_ = hash(ba)
        return self.hashes.get(hash_)


@tag('selenium')
class DjangoTests(TestCase):
    def setUp(self):
        self.dc = DockerCompose("./docker-compose-test.yml").down().up().init()
        self.tmp = None
        #self.tmp = tempfile.mkdtemp(prefix='tmp', dir=Path.home())
        #service = webdriver.firefox.service.Service(service_args=[
        #    "--profile-root",
        #    self.tmp
        #])
        #self.driver = webdriver.Firefox(service=service)
        self.driver = webdriver.Chrome()

    def tearDown(self):
        self.driver.close()
        self.dc.down()
        if self.tmp is not None:
            os.rmdir(self.tmp)

    def test_onboard(self):
        # Upload Z-Stack images
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

        # attempt to count, get a refusal, so do the tutorial
        profile.check_cannot_count()
        tutorial = profile.go_tutorial()
        tutorial.check_text_contains('etched with acid'
        ).check_finish_not_available().go_next(
        ).check_text_contains('These are fission tracks'
        ).go_previous().check_text_contains('etched with acid'
        ).go_next().check_text_contains('These are fission tracks'
        ).check_finish_not_available().go_next(
        ).check_text_contains('too small to distinguish'
        ).check_finish_not_available().go_next(
        ).check_text_contains('crystal defect'
        ).check_finish_not_available().go_next(
        ).check_text_contains('outside the region of interest'
        ).check_finish_available().go_finish().check()
        navbar.logout()

        # do the same thing with John
        profile = SignInPage(self.driver).go().sign_in(project_user)
        profile.check_cannot_count().go_tutorial().get_to_end_and_finish().wait()
        profile.go().check_can_count()
        navbar.logout()

        # check guest cannot count
        HomePage(self.driver).become_guest().check_cannot_count(
        ).go_tutorial().get_to_end_and_finish().check()
        # but then can
        HomePage(self.driver).become_guest()
        CountingPage(self.driver).check()
        # but then cannot
        navbar.logout()
        HomePage(self.driver).become_guest().check_cannot_count()

        # check we can still get counting after logging back in
        navbar.logout()
        counting = SignInPage(self.driver).go().sign_in(test_user).go_start_counting().check()

        # start counting tracks
        self.assertEqual(uploader.get_index(counting.image_displayed_url()), 1)
        self.assertEqual(uploader.get_index(counting.drag_layer_handle(0.33).image_displayed_url()), 2)
        self.assertEqual(uploader.get_index(counting.drag_layer_handle(0.67).image_displayed_url()), 4)
        self.assertEqual(uploader.get_index(counting.drag_layer_handle(-0.33).image_displayed_url()), 3)
        counting.check_count("000")
        self.assertFalse(counting.undo_available())
        self.assertFalse(counting.redo_available())
        counting.click_at(0.6, 0.35)
        counting.check_count("001")
        self.assertTrue(counting.undo_available())
        self.assertFalse(counting.redo_available())
        counting.undo()
        self.assertFalse(counting.undo_available())
        self.assertTrue(counting.redo_available())
        counting.redo()
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
        self.assertTrue(counting.undo_available())
        counting.undo()
        counting.check_count("004")
        self.assertTrue(counting.undo_available())
        self.assertTrue(counting.redo_available())
        counting.undo()
        counting.check_count("003")
        counting.redo()
        counting.check_count("004")
        counting.redo()
        counting.check_count("003")
        self.assertTrue(counting.undo_available())
        self.assertFalse(counting.redo_available())
        counting.undo()
        counting.check_count("004")
        counting.click_at(0.54, 0.35)
        counting.check_count("005")
        self.assertFalse(counting.redo_available())
        self.assertTrue(counting.undo_available())

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
        counting.go().check_count("000")
        navbar.check().logout()

        # login as test user, we should still see the saved result
        profile = SignInPage(self.driver).go().sign_in(test_user)
        counting = profile.go_start_counting().check()
        counting.check_count("005")

        # submit the result
        counting.submit()

        # see this result, as project admin
        navbar.logout()
        profile = SignInPage(self.driver).go().sign_in(project_user)
        report = navbar.go_manage_projects()
        report.toggle_tree_node("p1")
        report.select_tree_node("s1")
        self.assertEqual(report.result("1"), "5")
