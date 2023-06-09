#!/usr/bin/env python3
import csv
import os

from neo4j import GraphDatabase
from neo4j.exceptions import ConstraintError

class TwitterApp(object):

    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self._create_constraints()

    def close(self):
        self.driver.close()

    def _create_constraints(self):
        with self.driver.session() as session:
            session.run("CREATE CONSTRAINT unique_user IF NOT EXISTS FOR (u:User) REQUIRE u.username IS UNIQUE")
            session.run("CREATE CONSTRAINT unique_tweet IF NOT EXISTS FOR (t:Tweet) REQUIRE t.id IS UNIQUE")
            session.run("CREATE CONSTRAINT unique_hashtag IF NOT EXISTS FOR (h:Hashtag) REQUIRE h.hashtag IS UNIQUE")
            session.run("CREATE CONSTRAINT unique_country IF NOT EXISTS FOR (c:Country) REQUIRE c.name IS UNIQUE")

    def _create_user_node(self, username):
        with self.driver.session() as session:
            try:
                session.run("CREATE (u:User {username: $username})", username=username)
            except ConstraintError:
                pass

    def _create_tweet_node(self, _id, tweet):
        with self.driver.session() as session:
            try:
                session.run("CREATE (t:Tweet {_id: $_id, tweet: $tweet})", _id=_id, tweet=tweet)
            except ConstraintError:
                pass

    def _create_country_node(self, country):
        with self.driver.session() as session:
            try:
                session.run("CREATE (c:Country {name: $country})", country=country)
            except ConstraintError:
                pass

    def _create_hashtag_node(self, hashtag):
        with self.driver.session() as session:
            try:
                session.run("CREATE (h:Hashtag {hashtag: $hashtag})", hashtag=hashtag)
            except ConstraintError:
                pass

    def _create_user_to_hashtag_relationship(self, username, hashtag, timestamp):
        with self.driver.session() as session:
            session.run("""
                MATCH (u:User), (h:Hashtag)
                WHERE u.username=$username AND h.hashtag=$hashtag
                CREATE (u)-[r:USED_HASHTAG {timestamp: $timestamp}]->(h)
                RETURN type(r)""", username=username, hashtag=hashtag, timestamp=timestamp)


    def _create_user_to_user_relationship(self, username, mentioned, timestamp):
        with self.driver.session() as session:
            session.run("""
                MATCH (u1:User), (u2:User)
                WHERE u1.username=$username AND u2.username=$mentioned
                CREATE (u1)-[r:MENTIONED {timestamp: $timestamp}]->(u2)
                RETURN type(r)""", username=username, mentioned=mentioned, timestamp=timestamp)

    def _create_user_to_country_relationship(self, username, country):
        with self.driver.session() as session:
            session.run("""
                MATCH (u:User), (c:Country)
                WHERE u.username=$username AND c.name=$country
                CREATE (u)-[r:FROM]->(c)
                RETURN type(r)""", username=username, country=country)

    def _create_user_to_tweet_relationship(self, username, _id, timestamp):
        with self.driver.session() as session:
            session.run("""
                MATCH (u:User), (t:Tweet)
                WHERE u.username=$username AND t._id=$_id
                CREATE (u)-[r:TWEETED {timestamp: $timestamp}]->(t)
                RETURN type(r)""", username=username, _id=_id, timestamp=timestamp)

    def init(self, source):
        with open(source, newline='') as csv_file:
            reader = csv.DictReader(csv_file,  delimiter='|')
            for r in reader:
                self._create_user_node(r["handle"])
                self._create_tweet_node(r["tweet_id"], r["tweet"])
                self._create_country_node(r["country"])
                tweet_tokens = r["tweet"].split()
                for token in tweet_tokens:
                    if token.startswith("#"):
                        self._create_hashtag_node(token)
                        self._create_user_to_hashtag_relationship(r["handle"], token, r["date"])
                    if token.startswith('@'):
                        self._create_user_node(token)
                        self._create_user_to_user_relationship(r["handle"], token, r["date"])
                self._create_user_to_tweet_relationship(r["handle"], r["tweet_id"], r["date"])
                self._create_user_to_country_relationship(r["handle"], r["country"])


    def _search_user(self, tx, username):
        res = tx.run("""
            MATCH (u:User)
            WHERE u.username=$username
            RETURN u
        """, username=username)
        records = list(res)
        summary = res.consume()
        return records, summary

    def search_user(self, username):
        with self.driver.session() as session:
            records, summary = session.execute_read(self._search_user, username)
            print("Results:", len(records))
            print("Summary Query:", summary.query)
            print("Transaction Time (ms):", summary.result_available_after)
            for user in records:
                print(user.data())


def print_menu():
    mm_option = {
        1: "Load graph data",
        2: "Search user",
        3: "Exit",
    }
    for key in mm_option.keys():
        print(key, '--', mm_option[key])


if __name__ == "__main__":
    # Read connection env variables
    neo4j_uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
    neo4j_user = os.getenv('NEO4J_USER', 'neo4j')
    neo4j_password = os.getenv('NEO4J_PASSWORD', 'iteso@123')

    twitter = TwitterApp(neo4j_uri, neo4j_user, neo4j_password)
    print("Twitter App Graph")
    while(True):
        print_menu()
        option = int(input("Select an option: "))
        if option == 1:
            twitter.init("data/tweets.csv")
        elif option == 2:
            username = input("Enter username: ")
            twitter.search_user(username)
        elif option == 3:
            twitter.close()
            exit(0)

